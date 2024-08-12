# for better logging
import logging
# has setup for format that is pretty good looking 
import src.utils.LoggingHelper as logHelper
# asyncs
import asyncio
# timed things like TTL
from datetime import datetime, timedelta
# for identifying if functions are coroutines for callbacks
import inspect
# typing annotations to help writing
import typing
# copying GraphNode settings to protect objects
import copy

import src.DialogNodeParsing as nodeParser

import src.utils.CallbackUtils as CbUtils
import src.BuiltinFuncs.BaseFuncs as BaseFuncs
# annotating function purposes
from src.utils.Enums import POSSIBLE_PURPOSES, CLEANING_STATE, ITEM_STATUS, TASK_STATE

import src.utils.SessionData as SessionData
import src.utils.TimeoutTask as TimeoutTask
# validating function data
from jsonschema import validate, ValidationError
# type annotations
import src.DialogNodes.BaseType as BaseType

import src.utils.Cache as Cache


dialog_logger = logging.getLogger('Dev-Handler-Reporting')
logHelper.use_default_setup(dialog_logger)
dialog_logger.setLevel(logging.INFO)
#Debug is alllll the details of current state

#cleaning is probably going to get really spammy so putting that in its own separate one to make debugging easier
cleaning_logger = logging.getLogger("Dialog Cleaning")
logHelper.use_default_setup(cleaning_logger)
cleaning_logger.setLevel(logging.INFO)

execution_reporting = logging.getLogger('Handler Reporting')
logHelper.use_default_setup(execution_reporting)
execution_reporting.setLevel(logging.DEBUG)

#TODO: yaml support for what events want to throw during transitions?
#TODO: allow yaml names to have scope and qualified names stuff ie parse . in names
#TODO: exception handling, how to direct output
#TODO: maybe fix cleaning so it doesn't stop if one node excepts? but what to do with that node that excepts when trying to stop and clear?
#TODO: sessions making sure they work as intended
#TODO: create modal support
#TODO: saving and loading active nodes
#TODO: maybe transition callback functions have a transition info paramter?
#TODO: Templating yaml?
#TODO: go through code fine sweep for anything that could be changing data meant to be read
#TODO: during transition order is to section session which closes node which has only one set way to close every time then does transition callbacks.
#       This causes a flickering of buttons on discord menu message. Can I get that to not happen somehow? Can i get more info to close node so it can pass it to callbacks about why it's called?
#       tho at least close_node knowing why it was calle would be good for debugging
#TODO: make callback permitted purposes more precise
#TODO: bug timeout as event, if you specify should close in handling it doesn't recognize timeout when closing node anymore

#NOTE: each active node will get a reference to handler. Be careful what callbacks are added as they can mess around with handler itself

# Thoughts:
#   sapwning multiple active nodes of same graph node, transitions assume different graph nodes
#   game (send dms that each player selects action on to each person, ie warewolf, mafia) might use above case.
#       probably more useful than at beginning spawing one for everyone and syncing it to have main game turn spawn separate nodes asking each player for their turn actions
#   local broad casting event to subset
# tracking node execution progress

class DialogHandler():
    def __init__(self, graph_nodes:"typing.Optional[dict[str, BaseType.BaseGraphNode]]"=None, functions=None, settings=None, pass_to_callbacks=None, **kwargs) -> None:
        dialog_logger.debug(f"dialog handler being initialized, id is <{id(self)}>")
        self.graph_node_indexer = Cache.MultiIndexer(
                cache=graph_nodes,
                input_secondary_indices=[
                    Cache.FieldValueIndex("type", keys_value_finder=lambda x: x.TYPE),
                    Cache.FieldValueIndex("functions", keys_value_finder=lambda x: x.TYPE)
                ]
        )
        '''maps the string node id from yaml to graph node object.'''
        dialog_logger.debug(f"dialog handler <{id(self)}> initializing with GraphNode cache <{id(self.graph_node_indexer.cache)}> with <{len(self.graph_node_indexer.cache)}> nodes registered")
        self.functions_cache = Cache.MultiIndexer(cache=functions, input_secondary_indices=[
                Cache.FieldValueIndex("sections", keys_value_finder=lambda x: x["permitted_purposes"])
            ]
        )
        '''store of functions this handler is allowed to call. other handlers linking to same list is ok and on dev to handle.
        maps function reference name to dict of function reference and other overidden settings'''

        self.active_node_cache = Cache.MultiIndexer(
                input_secondary_indices=[
                    Cache.FieldValueIndex("graph_node", keys_value_finder=lambda x: x.graph_node.id),
                    Cache.FieldValueIndex("event_forwarding", keys_value_finder=lambda x: list(x.graph_node.events.keys())),
                    Cache.ObjContainsFieldIndex("session", keys_value_finder=lambda x: x.session)
                ]
        )
        '''store for all active nodes this handler is in charge of handling events on. is mapping of unique id to a dictionary holding active node object and handler data for it'''

        self.timeouts_tracker = dict()

        self._event_queue = []
        #TODO: still need to integrate and use these settings everywhere, especially the reading sections
        #       but before doing that probably want to think through what reporting will look like, where should reports go: dev, operator, server logs, bot logs?
        self.settings = copy.deepcopy(settings) if settings is not None else {}
        if "exception_level" not in self.settings:
            self.settings["exception_level"] = "ignore"

        self.cleaning_task = None

        self.register_module(BaseFuncs)

        self.pass_to_callbacks = pass_to_callbacks if pass_to_callbacks else {}
        '''data that handler should add on to pass to any callbacks it handles'''

        # passed in as extra settings
        for key, option in kwargs.items():
            if hasattr(self, key):
                raise Exception(f"trying to add extra attribute {key} but conflicts with existing attribute")
            setattr(self, key, option)

    '''#############################################################################################
    ################################################################################################
    ####                                   SETUP GRAPH NODES SECTION
    ################################################################################################
    ################################################################################################'''

    def setup_from_files(self, file_names:"list[str]" = []):
        '''clear out current graph nodes and replace with nodes in the passed in files. Raises error if nodes have double definitions in listed files
          or graph node definition badly formatted.'''
        #TODO: second pass ok and debug running
        self.graph_node_indexer.clear()
        nodeParser.parse_files(*file_names, existing_nodes=self.graph_node_indexer.cache)

    def add_graph_nodes(self, node_list:"dict[str, BaseType.BaseGraphNode]"={}, overwrites_ok=False):
        '''add all nodes in list into handler. gives a warning on duplicates
         dev note: assumed handler is now responsible for the objects passed in'''
        #TODO: second pass ok and debug running
        for node_id, node in node_list.items():
            if node.id in self.graph_node_indexer:
                if overwrites_ok:
                    self.graph_node_indexer.add_item(node_id, node)
                else:
                    # possible exception, want to have setting for whether or not it gets thrown
                    execution_reporting.warning(f"tried adding <{node.id}>, but is duplicate. ignoring it.")
                    continue
            else:
                self.graph_node_indexer.add_item(node_id, node)
    
    def add_files(self, file_names:"list[str]"=[]):
        #TODO: second pass ok and debug running
        # note if trying to create a setting to ignore redifinition exceptions, this won't work since can't sort out redefinitions exceptions from rest
        nodeParser.parse_files(*file_names, existing_nodes=self.graph_node_indexer.cache)
        self.graph_node_indexer.reindex()

    def reload_files(self, file_names:"list[str]"=[]):
        updated_nodes = nodeParser.parse_files(*file_names, existing_nodes={})
        for k, node in updated_nodes.items():
            execution_reporting.info(f"updated/created node {node.id}")
            self.graph_node_indexer.set_item(k, node)

    def final_validate(self):
        #TODO: maybe clean up and split so this can do minimal work on new nodes? or maybe just wait until someone adds all nodes?
        #TODO: smarter caching of what is validated

        def validate_function_list(func_list, node_id, purpose, string_rep, event_type=None):
            for callback in func_list:
                if type(callback) is str:
                    func_name = callback
                    args = None
                else:
                    func_name = list(callback.keys())[0]
                    args = callback[func_name]
                
                #TODO: check event type and node type once that's implemented
                if func_name == "or" or func_name == "and" and purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                    validate_function_list(args, node_id, purpose, string_rep, event_type=event_type)
                    continue

                if not self.function_is_permitted(func_name, purpose):
                    raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep} but isn't allowed to run there")
                # function has to exist at this point because the check checks for that
                func_ref = self.functions_cache.get(func_name)[0]["ref"]
                if func_ref.has_parameter == "always" and args is None:
                    raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep}, missing required arguments")
                elif func_ref.has_parameter is None and args is not None:
                    raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep}, function not meant to take arguments, extra values passed")
                
                if args is not None:
                    try:
                        validate(args, func_ref.schema)
                    except ValidationError as ve:
                        path_elements = [str(x) for x in ve.absolute_path]
                        path = string_rep
                        if len(path_elements) > 0:
                            path+="."+'.'.join(path_elements)
                        except_message = f"Exception in verifying node {node_id}, "\
                                        f"yaml definition provided for function {func_name} listed in section {string_rep} does not fit expected format "\
                                        f"error message: {ve.message}"
                        raise Exception(except_message)

        explored=set()
        dependent=set()
        for node_id, graph_node in self.graph_node_indexer.cache.items():
            next_nodes, function_lists = graph_node.validate_node()
            for function_list in function_lists:
                validate_function_list(*function_list)
            explored.add(node_id)
            if node_id in dependent:
                dependent.remove(node_id)
            for next_node in next_nodes:
                if next_node not in explored:
                    dependent.add(next_node)

        if len(dependent) > 0:
            raise Exception(f"handler {id(self)} tried to validate the graph it has, but left with hanging transitions. missing nodes: {dependent}")

    '''#############################################################################################
    ################################################################################################
    ####                                  MANAGING CALLBACK FUNCTIONS SECTION
    ################################################################################################
    ################################################################################################'''

    def register_function(self, func, override_settings={}):
        '''register a function as allowed to use by this handler. Can override some of the function's default settings
        
        Parameters
        ---
        * func - `callable`
            function that you want handler to be able to call. Must have fields attached that hold configuration settings for how 
            function works in handler. see CallbackUtils for settings
        * override_settings -  `dict[str, Any]`
            dict holding setting name to settings this handler should override function's default ones with. currently only looks for
            'allowed_sections' and 'cb_key'
            
        Return
        ---
        boolean for if function was successfully registered'''
        permitted_purposes = func.allowed_sections
        if "allowed_sections" in override_settings:
            permitted_purposes = copy.deepcopy(override_settings["allowed_sections"])

        if permitted_purposes is None or len(permitted_purposes) < 1:
            execution_reporting.warning(f"dialog handler tried registering a function <{func.__name__}> that does not have any permitted sections")
            return False
        if func == self.register_function:
            execution_reporting.warning("dialog handler tried registering own registration function, dropping for security reasions")
            return False

        cb_key = func.cb_key
        if "cb_key" in override_settings:
            execution_reporting.warning(f"doing manual override to register function with key <{override_settings['cb_key']}> instead of usual <{cb_key}>")
            cb_key = override_settings["cb_key"]
        if cb_key in self.functions_cache:
            # this is an exception so that developer can know as soon as possible instead of silently ignoring second one and causeing confusion 
            # why the function isn't being called
            raise Exception(f"trying to register function <{func.__name__}> with key <{cb_key}> but key already registered. " +\
                                        f"If trying to register a different function than what is registered already, change the key you are registering with. "+ \
                                        "Be aware yaml has to match the key registered with")

        dialog_logger.debug(f"dialog handler id'd {id(self)} registered callback <{func}> with key <{cb_key}> {'same as default,' if cb_key == func.cb_key else 'overridden,'} for purposes: " +\
                            f"<{[purpose.name for purpose in permitted_purposes]}> {'same as default' if permitted_purposes == func.allowed_sections else 'overridden'}")
        #TODO: this needs upgrading if doing qualified names
        self.functions_cache.add_item(cb_key, {"ref": func, "permitted_purposes": permitted_purposes, "registered_key": cb_key})
        return True

    def register_functions(self, function_overrides):
        '''registers a group of functions. 
        
        Parameters
        ---
        * function_overrides - `dict[callable, dict[str, Any]]
            mapping of the function to any override settings to register that function with
            
        Return
        ---
        list of functions that were added'''
        functions_registered = []
        for func, overrides in function_overrides.items():
            result = self.register_function(func, overrides)
            if result:
                functions_registered.append(func)
        return functions_registered

    def register_module(self, module):
        '''registers functions from module. module must have a variable called "dialog_func_info" that holds mapping of functions 
        to overrides, and only those funcitons from module are registered'''
        return self.register_functions(module.dialog_func_info)

    def function_is_permitted(self, func_key:str, purpose:POSSIBLE_PURPOSES, escalate_errors=False):
        '''
        Checks if function is allowed to run for the given section.

        Return
        ---
        `bool` - if function is registered in handler and is permitted to run in the given section of handling. 
        False if function is not registered, false if registered and not permitted'''
        if func_key not in self.functions_cache:
            execution_reporting.error(f"checking if <{func_key}> can run during phase <{purpose}> but it is not registered")
            if escalate_errors:
                raise Exception(f"checking if <{func_key}> can run during phase {purpose} but it is not registered")
            return False
        if purpose not in self.functions_cache.get_ref(func_key)["permitted_purposes"]:
            # note, not accessing function.allowed_sections because this field contains overridden values from registering
            execution_reporting.warn(f"checking if <{func_key}> can run during phase <{purpose}> but it is not allowed")
            if escalate_errors:
                raise Exception(f"checking if <{func_key}> can run during phase {purpose} but it is not allowed")
            return False
        return True

    '''#############################################################################################
    ################################################################################################
    ####                                   EVENTS HANDLING SECTION
    ################################################################################################
    ################################################################################################'''

    async def start_at(self, node_id:str, event_key:str, event):
        '''start the graph execution at the given node with given event. checks if node exists and operation is allowed.'''
        # keeping this separate from event handling process to reduce work per event 
        # start is set up so that it has to call start callbacks and setup session before filters, events dont have start callbacks they are straight into filters then event callbacks.

        # first level filters for can start
        execution_reporting.info(f"dialog handler id'd <{id(self)}> starting process to start at node <{node_id}> with event <{event_key}> event deets: id <{id(event)}> type <{type(event)}> <{event}>")
        dialog_logger.debug(f"more deets for event at start at function <{event.content if hasattr(event, 'content') else 'content N/A'}>")
        if node_id not in self.graph_node_indexer:
            execution_reporting.warn(f"cannot start at <{node_id}>, not valid node")
            return None
        graph_node:BaseType.BaseGraphNode = self.graph_node_indexer.get_ref(node_id)
        if not graph_node.is_graph_start(event_key):
            execution_reporting.warn(f"cannot start at <{node_id}>, settings do not allow either starting at node or starting with event type <{event_key}>")
            return None
        
        # process session before node since the activation process binds session and currently don't have a neat written out process to bind new session
        session:typing.Union[SessionData.SessionData, None] = None
        if graph_node.graph_starts_with_session(event_key):
            default_session_duration = graph_node.get_graph_start_session_TTL(event_key)
            if default_session_duration is not None:
                execution_reporting.info(f"dialog handler id'd <{id(self)}> start at node <{node_id}> with event <{event_key}> found yaml defines session TTL")
                session = SessionData.SessionData(timeout_duration=timedelta(seconds=default_session_duration))
            else:
                session = SessionData.SessionData()
            dialog_logger.info(f"dialog handler id'd <{id(self)}> node <{node_id}> with event <{event_key}> id <{id(event)}> start at found node starts with a session, created it. id: <{id(session)}> timeout <{session.timeout}>")
        
        # get active node at this graph node.
        #   design of callbacks is they assume they have an active node to act on. Allowing reusing those for start section (and reducing functions
        #   to maintain/store) means want an active node before processing callbacks
        active_node:BaseType.BaseNode = graph_node.activate_node(session)
        if session is not None:
            # feels more right to set up session to mirror state of node (knowing of each other) before callbacks happen on them
            session.add_node(active_node)
        dialog_logger.debug(f"dialog handler id'd <{id(self)}> node <{node_id}> with event <{event_key}> id <{id(event)}> oject type <{type(event)}> has active node now <{id(active_node)}>, running callbacks")
        # some filters may want to depend on session data, which usually gets chance to setup on transition. Startup doesn't get any other chance
        #   than running some callbacks before filters
        await self._run_event_callbacks_on_node(active_node, event_key, event, version="start")
        dialog_logger.debug(f"dialog handler id'd <{id(self)}> node <{id(active_node)}><{node_id}> with event <{event_key}> id <{id(event)}> oject type <{type(event)}> starting custom filter process")
        start_filters_result = self._run_event_filters_on_node(active_node, event_key, event, version="start")
        if not start_filters_result:
            if session is not None:
                # there's a circular reference by design, break it if it was created and node failed filters so garbage collector can get it
                session.clear_session_history()
            return None
        await self._track_new_active_node(active_node, event)
        execution_reporting.info(f"started active version of <{node_id}>, unique id is <{id(active_node)}>")

    async def handle_event(self, event_key:str, event):
        '''entrypoint for event happening and getting node responses to event. Once handler is notified, it sends out the event info
        to all nodes that are waiting for that type of event.

        Parameters
        ---
        event_key - `str`
            the key used internally for what the event is
        event - `Any`
            the actual event data. handler itself doesn't care about what type it is, just make sure all the types of callback 
            specified via yaml can handle that type of event'''
        dialog_logger.info(f"handler id'd <{id(self)}> has been notified of event happening. event key <{event_key}> id'd <{id(event)}> oject type <{type(event)}>")
        waiting_node_keys = self.active_node_cache.get_keys(event_key, index_name="event_forwarding", default=[])
        dialog_logger.debug(f"handler id'd <{id(self)}>, event id'd <{id(event)}> nodes waiting for event <{event_key}> are <{[f'<{str(id(self.active_node_cache.get_ref(x)))}><{self.active_node_cache.get_ref(x).graph_node.id}>' for x in waiting_node_keys]}>")
        # don't use gather here, think it batches it so all nodes responding to event have to pass callbacks before any one of them go on to transitions
        # each node is mostly independent of others for each event and don't want them to wait for another node to finish
        notify_results = await asyncio.gather(*[self._run_event_on_node(self.active_node_cache.get_ref(a_n_key), event_key, event) for a_n_key in waiting_node_keys])
        dialog_logger.debug(f"handler id'd <{id(self)}>, event id'd <{id(event)}> end of handle_event results are <{notify_results}>")

    def notify_event(self, event_key, event):
        event_loop = asyncio.get_event_loop()
        task = event_loop.create_task(self.handle_event(event_key, event))
        self._event_queue.append(task)

    '''#############################################################################################
    ################################################################################################
    ####                                       RUNNING EVENTS SECTION
    ################################################################################################
    ################################################################################################'''

    async def _run_event_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''processes event happening on the given node'''
        execution_reporting.debug(f"handler id'd <{id(self)}> running event <{id(event)}><{event_key}><{type(event)}> on node <{id(active_node)}><{active_node.graph_node.id}>")
        debugging_phase = " running filters"
        # try: #try catch around whole event running, got tired of it being hard to trace Exceptions so removed
        filter_result = self._run_event_filters_on_node(active_node, event_key, event)
        if not filter_result:
            return
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> passed filter stage")

        debugging_phase = "running callbacks"
        callback_close_commands = await self._run_event_callbacks_on_node(active_node, event_key, event)
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> finished event callbacks")

        debugging_phase = "transitions"
        transition_result = await self._run_transitions_on_node(active_node, event_key, event)
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> finished transitions")

        # checking if should close after event, combine event schedule_close flag and what was returned fron transitions
        close_flag = active_node.graph_node.get_event_close_flags(event_key)
        #TODO: double check how want to combine these
        should_close_node = ("node" in close_flag) or transition_result["node"] or callback_close_commands["close_node"]
        should_close_session = ("session" in close_flag) or transition_result["session"] or callback_close_commands["close_session"]
        if should_close_node and active_node.is_active():
            debugging_phase = "closing"
            await self.close_node(active_node, timed_out=False)

        if should_close_session and active_node.session is not None:
            debugging_phase = "closing session"
            execution_reporting.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> event handling closing session")
            await self.close_session(active_node.session)
        # except Exception as e:
        #     execution_reporting.warning(f"failed to handle event on node at stage {debugging_phase}")
        #     exc_type, exc_obj, exc_tb = sys.exc_info()
        #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #     print(exc_type, fname, exc_tb.tb_lineno)
        #     dialog_logger.info(f"exception on handling event on node <{id(active_node)}> node details: <{vars(active_node)}> exception:<{e}>")

    def _run_event_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, version:typing.Union[str, None] = None):
        '''runs all custom filter callbacks for either starting at node with given event or for the given node and event pair. Filters are all syncronous callbacks.
        Catches and logs all errors from trying to run functions, stops going through list immediately
        
        Parameters:
        ---
        version - `str`
            "start", or None. specifies which list to run: starting graph at this node filters, or regular for given event'''
        dialog_logger.debug(f"handler id'd <{id(self)}> running event filters. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, type of event <{type(event)}> filters: <{active_node.graph_node.get_event_filters(event_key)}>")
        
        if version == "start":
            dialog_logger.debug(f"running start version of filters on node <{id(active_node)}><{active_node.graph_node.id}>, start filters are {active_node.graph_node.get_graph_start_filters(event_key)}")
            node_filters = active_node.graph_node.get_graph_start_filters(event_key)
        else:
            node_filters = active_node.graph_node.get_event_filters(event_key)
            #custom event types designed to have extra addon filters, still being fleshed out as of 3.6.0
            # if hasattr(event, "get_event_filters") and callable(event.get_event_filters):
            #     node_filters = event.get_event_filters()
            #     dialog_logger.debug(f"filters from custom event {node_filters}")
            # else:
            #     node_filters = []
        execution_reporting.debug(f"custom filter list for node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}> is <{node_filters}>")

        try:
            return self._filter_list_runner(active_node, event, node_filters, purpose=POSSIBLE_PURPOSES.FILTER)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")
            return False
    

    async def _run_event_callbacks_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, version:typing.Union[str, None] = None):
        '''helper that runs the list of custom callback actions of the specified version for a node event pair. Catches and logs any errors from 
        attempting to run the custom callbacks, stops going through list immediately and returns.
        
        Parameters:
        ---
        active_node - `BaseType.BaseNode`
            the active node instance to run events on. start callbacks runs when this isn't being tracked by handler yet
        version - `str`
            "start", "close", or None. specifies which list to run: start setup for event, close callbacks, or regular for given event
            
        Returns
        ---
        Returns callbacks' modifications to flags for whether or not should close node and/or session. Format is `{"close_node": bool, "close_session": bool}`. System
        combines these 'should close' flags by OR'ing them together. Only the regular event callbacks (ie when version = None) acutally use the return values'''
        if version == "start":
            callbacks = active_node.graph_node.get_graph_start_setup(event_key)
            execution_reporting.debug(f"running start callbacks. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        elif version == "close":
            callbacks = active_node.graph_node.get_node_close_actions()
            execution_reporting.debug(f"running closing callbacks. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        else:
            callbacks = active_node.graph_node.get_event_actions(event_key)
            execution_reporting.debug(f"running event callback. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        
        old_node_timeout = copy.deepcopy(active_node.timeout) if active_node.timeout is not None else None
        old_session_timeout = copy.deepcopy(active_node.session.timeout) if active_node.session is not None and active_node.session.timeout is not None else None
        before_callbacks_keys = self.active_node_cache.get_all_secondary_keys(id(active_node))
        try:
            action_results = await self._action_list_runner(active_node, event, callbacks, POSSIBLE_PURPOSES.ACTION)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")
            return {"close_node": False, "close_session": False}
        # in case there were updates that caused changes to keys, shouldn't break anything if no changes made
        if id(active_node) in self.active_node_cache:
            self.active_node_cache.set_item(id(active_node), active_node, before_callbacks_keys)
        if version is None:
            # only regular event callbacks should check updating timeout trackers
            # start callbacks may change timeout but they haven't been recorded inside tracking yet so that cannot be update call
            self.update_timeout_tracker(active_node, old_node_timeout)
            if active_node.session is not None:
                self.update_timeout_tracker(active_node.session, old_session_timeout)
        return action_results
    
    def _run_transition_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        node_transitions = active_node.graph_node.get_transitions(event_key)
        passed_transition = None
        for transition_ind, transition in enumerate(node_transitions):
            dialog_logger.debug(f"starting checking transtion number <{transition_ind}>")
            yaml_named_counts = BaseType.BaseGraphNode.parse_node_names(transition["node_names"])
            if "transition_counters" in transition:
                count_results = self._counter_runner(yaml_named_counts, active_node, event, transition["transition_counters"], POSSIBLE_PURPOSES.TRANSITION_COUNTER)
                dialog_logger.debug(f"counters finished executing for transition <{transition_ind}>, counts are {count_results}, to loop through <{count_results.keys()}>")
            else:
                count_results = yaml_named_counts
                dialog_logger.debug(f"no counters for transition <{transition_ind}>, counts are {count_results}, to loop through <{count_results.keys()}>")
            
            # clean up counts
            for node_name in list(count_results.keys()):
                if node_name not in self.graph_node_indexer:
                    execution_reporting.warning(f"active node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}> transition won't work, goal node doesn't exist. transition indexed <{transition_ind}>")
                    del count_results[node_name]
            
            # running filters on this transtition
            filter_res = True
            if "transition_filters" in transition:
                execution_reporting.debug(f"active node <{id(active_node)}><{active_node.graph_node.id}> to <{count_results}> has transition filters {transition['transition_filters']}")
                try:
                    filter_res = self._filter_list_runner(active_node, event, transition["transition_filters"], POSSIBLE_PURPOSES.TRANSITION_FILTER, goal_node=count_results)
                    if not isinstance(filter_res, bool):
                        filter_res = False
                except Exception as e:
                    filter_res = False
                    execution_reporting.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{count_results}>. assuming skip")
                    dialog_logger.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{count_results}>, details {e}")
            
            if filter_res:
                transition_close_flag = []
                if "schedule_close" in transition:
                    transition_close_flag = transition["schedule_close"]
                    if isinstance(transition["schedule_close"], str):
                        transition_close_flag = [transition_close_flag]
                passed_transition = {
                    "count": count_results,
                    "actions": transition["transition_actions"],
                    "session_action": (transition["session_chaining"] if isinstance(transition["session_chaining"], str) else list(transition["session_chaining"].keys())[0])
                                    if "session_chaining" in transition else "end",
                    "session_timeout": None if "session_chaining" not in transition or isinstance(transition["session_chaining"], str) else list(transition["session_chaining"].values())[0],
                    "close_flags": transition_close_flag,
                }
                return passed_transition
        return None
        
    async def _run_transitions_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        passed_transition = self._run_transition_filters_on_node(active_node, event_key, event)
        if passed_transition is None:
            return {"node": False, "session": False}
        dialog_logger.debug(f"transitions for node <{id(active_node)}><{active_node.graph_node.id}> that passed filters are for nodes <{passed_transition['count']}>, now starting transitions")

        section_exceptions = []
        callbacks_list:list[typing.Tuple[BaseType.BaseNode, list, int]] = []
        # first pass is setting up active nodes and sessiosn for callbacks to work on
        session_action = passed_transition["session_action"]
        session_timeout = passed_transition["session_timeout"]
        for next_node_name, count in passed_transition["count"].items():
            for i in range(count):
                session = None
                if session_action == "start" or (session_action == "chain" and active_node.session is None):
                    dialog_logger.info(f"starting session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{next_node_name}>")
                    if session_timeout is not None:
                        session = SessionData.SessionData(timeout_duration=timedelta(seconds=session_timeout))
                    else:
                        session = SessionData.SessionData()
                    dialog_logger.debug(f"session debugging, started new session, id is <{id(session)}>")
                elif session_action in ["chain", "section"] and active_node.session is not None:
                    if session_timeout is not None:
                        old_session_timeout = copy.deepcopy(active_node.session.timeout) if active_node.session.timeout is not None else None
                        active_node.session.set_TTL(timeout_duration=timedelta(seconds=session_timeout))
                        self.update_timeout_tracker(active_node.session, old_session_timeout)
                        session = active_node.session
                elif session_action != "end":
                    session = active_node.session
            next_node = self.graph_node_indexer.get_ref(next_node_name).activate_node(session)
            if session_action == "section" and session is not None:
                # not the complete list of all nodes created. might miss sone when ending session, might have extra when starting session but at least covers all that would be in the session about to be sectioned
                section_exceptions.append(next_node)
            execution_reporting.info(f"activated next node, is of graph node <{next_node_name}>, copy number <{i + 1}> id'd <{id(next_node)}>")
            if session_action != "end" and session is not None:
                # only end doesn't want node added to session
                dialog_logger.info(f"adding next node to session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{next_node_name}>")
                session.add_node(next_node)
                dialog_logger.info(f"session debugging, session being chained. id <{id(session)}>, adding node <{id(next_node)}><{next_node.graph_node.id}> to it, now node list is <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
            callbacks_list.append((next_node, passed_transition["actions"], i))

        for callback_settings in callbacks_list:
            section_data = self.generate_action_control_data({"copy":callback_settings[2]})
            old_session_timeout = copy.deepcopy(callback_settings[0].session.timeout) if callback_settings[0].session is not None and callback_settings[0].session.timeout is not None else None
            await self._action_list_runner(active_node, event, callback_settings[1], POSSIBLE_PURPOSES.TRANSITION_ACTION, goal_node=callback_settings[0], control_data=section_data, section_name="transition_actions")
            if callback_settings[0].session is not None and id(callback_settings[0].session) in self.timeouts_tracker:
                self.update_timeout_tracker(callback_settings[0].session, old_session_timeout)
            await self._track_new_active_node(callback_settings[0], event)
            dialog_logger.debug(f"checking session data for next node, {callback_settings[0].session}")
        
        if session_action == "section" and active_node.session is not None:
            await self.clear_session_history(active_node.session, exceptions=section_exceptions)
        
        return {"node": "node" in  passed_transition["close_flags"], "session": "session" in  passed_transition["close_flags"]}


    '''#############################################################################################
    ################################################################################################
    ####                   I-DONT-REALLY-HAVE-A-NAME-BUT-IT-DOESNT-FIT-ELSEWHERE SECTION
    ################################################################################################
    ################################################################################################'''

    async def _track_new_active_node(self, active_node:BaseType.BaseNode, event):
        '''adds the given active node to handler's internal tracking. after this, node is fully considered being managed by this handler.
        adds node to handler's list of active nodes its currently is waiting on, does node actions for entering node, adds info about what events node
        is waiting for, and adds trackers for timeouts'''
        #TODO: fine tune id for active nodes
        dialog_logger.info(f"dialog handler id'd <{id(self)}> adding node <{id(active_node)}><{active_node.graph_node.id}> to internal tracking and running node callbacks")
        active_node.activate()
        if active_node.session is not None:
            active_node.session.activate()

        await self._action_list_runner(active_node, event, active_node.graph_node.get_node_actions(), POSSIBLE_PURPOSES.ACTION)
        
        self.create_timeout_tracker(active_node)
        if active_node.session is not None:
            if id(active_node.session) not in self.timeouts_tracker:
                # only tracks session timeout if it is new thing to track, assume outside needs to update if it is already tracked
                self.create_timeout_tracker(active_node.session)
        self.active_node_cache.add_item(id(active_node), active_node)
        
        # used to have autoremoval for nodes that aren't waiting for anything, but found there might be cases where want to keep node around
        # if len(active_node.graph_node.get_events()) < 1:
        #     await self.close_node(active_node, timed_out=False)


    async def close_node(self, active_node:BaseType.BaseNode, timed_out=False, emergency_remove=False):
        '''Goes through handler's process to close the given node. Calls the custom close callbacks if not emergency close mode, then removes node from
        internal trackers
        
        Parameters
        ---
        active_node - `BaseNode`
            the active node instance to close that is in this handler
        timed_out - `bool`
            whether or not the close call is because of timing out. this information gets passed to the callbacks
        emergency_remove - `bool`
            whether or not to skip the custom callbacks and go to removing node from tracking'''
        if not active_node.is_active():
            return
        active_node.notify_closing()
        execution_reporting.info(f"closing node <{id(active_node)}><{active_node.graph_node.id}> timed out? <{timed_out}>")
        if not emergency_remove:
            await self._run_event_callbacks_on_node(active_node, "close", {"timed_out":timed_out}, version="close")
            dialog_logger.info(f"finished custom callbacks closing <{id(active_node)}><{active_node.graph_node.id}>, clearing node from internal trackers")

        active_node.close()

        # this section closes the session if no other nodes in it are active. make sure sectioning session doesn't clear out all nodes
        if active_node.session and active_node.session is not None:
            execution_reporting.debug(f"closing node <{id(active_node)}><{active_node.graph_node.id}> checking linked session is dead <{id(active_node.session)}>")
            printing_active = [node.graph_node.id for node in active_node.session.get_linked_nodes()]
            dialog_logger.debug(f"linked nodes to check are <{[f'<{str(id(node))}><{node.graph_node.id}> <{node.is_active()}>' for node in active_node.session.get_linked_nodes()]}>")
            session_void = True
            for node in active_node.session.get_linked_nodes():
                if node.is_active():
                    session_void = False
                    break
            
            if session_void:
                execution_reporting.debug(f"closing node <{id(active_node)}><{active_node.graph_node.id}> linked session is dead <{id(active_node.session)}>")
                await self.close_session(active_node.session, timed_out=timed_out)

        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.cache.items()}
        dialog_logger.debug(f"before remove, state is active nodes are <{printing_active}>")
        # printing_forwarding = {event:[str(x)+' '+self.active_node_cache.get(x)[0].graph_node.id for x in nodes] for event, nodes in self.active_node_cache.items(index_name="event_forwarding")}
        # dialog_logger.debug(f"current state is event forwarding <{printing_forwarding}>")

        self.active_node_cache.remove_item(id(active_node))
        if id(active_node) in self.timeouts_tracker:
            if self.timeouts_tracker[id(active_node)].state == TASK_STATE.WAITING:
                self.timeouts_tracker[id(active_node)].cancel()
            del self.timeouts_tracker[id(active_node)]
        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.cache.items()}
        dialog_logger.debug(f"after remove, state is active nodes are <{printing_active}>")
        # printing_forwarding = {event:[str(x)+' '+self.active_node_cache.get(x)[0].graph_node.id for x in nodes] for event,nodes in self.active_node_cache.items(index_name="event_forwarding")}
        # dialog_logger.debug(f"after remove state is event forwarding <{printing_forwarding}>")
    
    async def clear_session_history(self, session:SessionData.SessionData, timed_out=False, exceptions=[]):
        '''closes all nodes in session that are still active and aren't in exception list'''
        for node in session.get_linked_nodes():
            if node.is_active() and node not in exceptions:
                await self.close_node(node, timed_out=timed_out)
        session.clear_session_history(exceptions)
    
    async def close_session(self, session:SessionData.SessionData, timed_out=False):
        if not session.is_active():
            return
        execution_reporting.debug(f"closing session <{id(session)}>, current nodes <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
        session.notify_closing()
        await self.clear_session_history(session, timed_out=timed_out)
        session.close()
        if id(session) in self.timeouts_tracker:
            task = self.timeouts_tracker[id(session)]
            if task.state == TASK_STATE.WAITING:
                task.cancel()
            del self.timeouts_tracker[id(session)]


    '''#############################################################################################
    ################################################################################################
    ####                                       FUNCTION CALLBACK HELPERS SECTION
    ################################################################################################
    ################################################################################################'''

    def generate_action_control_data(self, addons=None):
        section_data = {"close_node": False, "close_session": False}
        if addons:
            if isinstance(addons, dict):
                section_data.update(addons)
        return section_data


    async def _action_list_runner(self, active_node:BaseType.BaseNode, event, action_list, purpose: POSSIBLE_PURPOSES, goal_node=None, control_data=None, section_name="actions"):
        '''helper for running a section of action callbacks.

        As of v3.7 each section of action callbacks in yaml has a separate data structure for intermediary values.
        Intermediary values are not stored in node and are discarded after section finishes executing but can be accessed by any callback in that section
        
        Return
        ---
        dict results from callbacks that would affect system. currently holds `close_node` and `close_session`, both default to False'''
        if control_data is None:
            # object meant for temp just passing data to rest of functions in this section.
            control_data = self.generate_action_control_data()
        section_data = {}
        for callback in action_list:
            if isinstance(callback, str):
                # is just function name, no parameters
                await self._run_func_async(callback, purpose, active_node, event, goal_node=goal_node, callb_section_data=section_data, control_data=control_data, section_name=section_name)
            else:
                key = list(callback.keys())[0]
                value = callback[key]
                await self._run_func_async(key, purpose, active_node, event, goal_node=goal_node, base_parameter=value, callb_section_data=section_data, control_data=control_data, section_name=section_name)
        return control_data
    
    def _counter_runner(self, yaml_count, active_node:BaseType.BaseNode, event, action_list, purpose:POSSIBLE_PURPOSES):
        section_data = {}
        for callback in action_list:
            if isinstance(callback, str):
                # is just function name, no parameters
                self._run_func(callback, purpose, active_node, event, callb_section_data=section_data, section_name="transition_counters", control_data=yaml_count)
            else:
                key = list(callback.keys())[0]
                value = callback[key]
                self._run_func(key, purpose, active_node, event, base_parameter=value, callb_section_data=section_data, section_name="transition_counters", control_data=yaml_count)
            # cleanup the control data to what is expected
            for item in list(yaml_count.keys()):
                if not isinstance(yaml_count[item], int):
                    del yaml_count[item]
        return yaml_count


    def _filter_list_runner(self, active_node:BaseType.BaseNode, event, filter_list, purpose:POSSIBLE_PURPOSES,
                           goal_node=None, operator="and", section_data=None):
        '''
        helper for running a section of filter callbacks for given purpose, node, and event. 
        List of filter functions can have nested lists, but the keys for those nested lists have to be 'and' or 'or', which are built in keywords for 
        doing boolean operations on the nested function names. 
        Otherwise it treats the value as parameters to pass to the function named by the key.
        
        As of v3.7 each section of filters in yaml has a separate data structure for intermediary values (nested lists do not count as seperate sections for this functionalty)
        Intermediary values are not stored in node and are discarded after section finishes executing but can be accessed by any callback in that section
        
        Return
        ---
        'boolean' - if active node and event situation passes custom filter list'''
        if section_data is None:
            # object meant for temp just passing datat to rest of functions in this section.
            section_data = {}
        section_name = "filters" if purpose.value == POSSIBLE_PURPOSES.FILTER else "transition_filters"
        #TODO: figure out section progress data structure

        def recur_list_helper(func_sub_list, operator):
            for filter in func_sub_list:
                if isinstance(filter, str):
                    # is just function name, no parameters
                    filter_run_result = self._run_func(func_name=filter, purpose=purpose, active_node=active_node, event=event, goal_node=goal_node, callb_section_data=section_data, section_name=section_name)
                    if not isinstance(filter_run_result, bool):
                        filter_run_result = False
                else:
                    # is a dict representing function call with arguments or nested operator, should only have one key:value pair
                    key = list(filter.keys())[0]
                    value = filter[key]
                    if key in ["and", "or"]:
                        # special keywords that aren't function names and special meaning to handler
                        # filter_run_result = self._filter_list_runner(active_node, event, value, purpose, goal_node, operator=key, section_data=section_data)
                        filter_run_result = recur_list_helper(value, operator=key)
                    else:
                        # argument in vlaue is expected to be one object. a list, a dict, a string etc
                        filter_run_result = self._run_func(key, purpose, active_node, event, goal_node=goal_node, base_parameter=value, callb_section_data=section_data, section_name=section_name)
                        if not isinstance(filter_run_result, bool):
                            filter_run_result = False
                # find if hit early break because not possible to change result with rest of list
                if operator == "and" and not filter_run_result:
                    return False
                if operator == "or" and filter_run_result:
                    return True
            # end of for loop, means failed to find early break point
            if operator == "and":
                return True
            if operator == "or":
                return False
        return recur_list_helper(filter_list, operator)

    async def _run_func_async(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event,
                             goal_node:typing.Union[BaseType.BaseNode, str]=None, base_parameter=None, callb_section_data=None,
                             section_name="", control_data=None, section_progress=None):
        '''helper for setup and running a dialog callback that could be async. awaits result if asynchronous.
        check `_run_func` for details on parameters'''
        run_func_built = self._run_func(func_name=func_name, purpose=purpose, active_node=active_node, event=event,
                                       goal_node=goal_node, base_parameter=base_parameter, callb_section_data=callb_section_data,
                                       section_name=section_name, control_data=control_data, section_progress=section_progress)
        if inspect.isawaitable(run_func_built):
            return await run_func_built
        return run_func_built
    
    def _run_func(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, 
                 goal_node:"typing.Union[BaseType.BaseNode, dict[str,int]]"=None, base_parameter=None, callb_section_data=None, section_name="", control_data=None, section_progress=None):
        '''helper for setup and running a single callback. 
        func_name and purpose is for checking information on formatting, rest are values that dialog callbacks need
        Base parameter expected to be what is read in from yaml. Will be deep copied if there is data.
        section and control data are assumed to be managed by caller, which is usually the function section handlers'''
        if not self.function_is_permitted(func_name, purpose):
            dialog_logger.debug(f"Dialog handler id'd <{id(self)}> tried running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>, not allowed")
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                # filter functions, whether transtion or not, expect bool returns. must return some bool and assume not allowed
                # (function not listed in handler, or running for wrong purpose) means failed filter
                return False
            else:
                return None
        dialog_logger.debug(f"Dialog handler id'd <{id(self)}> starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>")
        func_ref = self.functions_cache.get(func_name)[0]["ref"]
        datapack = CbUtils.CallbackDatapack(
                                            active_node=active_node,
                                            event=event,
                                            base_parameter=copy.deepcopy(base_parameter) if base_parameter is not None else None,
                                            goal_node_name=goal_node if isinstance(goal_node, str) else None,
                                            goal_node=goal_node if not isinstance(goal_node, str) else None,
                                            section_name=section_name,
                                            section_data=callb_section_data if callb_section_data else {},
                                            control_data=control_data if control_data else {},
                                            section_progress=section_progress if section_progress else {},
                                            **self.pass_to_callbacks)
        return func_ref(datapack)
    
    '''#############################################################################################
    ################################################################################################
    ####                                       MANAGING HANDLER DATA SECTION
    ################################################################################################
    ################################################################################################'''

    def _get_waiting_nodes(self, event_key):
        '''gets list of active nodes waiting for certain event from handler'''
        return self.active_node_cache.get(event_key, index_name="event_forwarding", default=set())

    '''#############################################################################################
    ################################################################################################
    ####                                       CLEANING OUT NODES SECTION
    ################################################################################################
    ################################################################################################'''

    # TODO: is canceling needed and ok
    # TODO: runthrough of what happens, is there always one task, how to ensure less double running

    # there's only one task that handles organizing how to respond to timeout events

    def create_timeout_tracker(self,
                               timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData]):
        '''create task object that is responsible for firing tieout event on given node or session.
        Handler will keep track of the task'''
        if timeoutable.timeout is None:
            return
        if isinstance(timeoutable, BaseType.BaseNode):
            timeout_task = TimeoutTask.HandlerTimeoutTask(
                    timeoutable=timeoutable,
                    timeout_handler=self.single_node_timeout_handler,
                    close_handler=self.single_node_timeout_close_handler)
        else:
            timeout_task = TimeoutTask.HandlerTimeoutTask(
                    timeoutable=timeoutable,
                    timeout_handler=self.single_session_timeout_handler,
                    close_handler=self.single_session_timeout_close_handler)
        self.timeouts_tracker[id(timeoutable)] = timeout_task

    def update_timeout_tracker(self,
                               timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData],
                               old_timeout):
        '''updates internal tracking if there are changes to timeout that would cause significant difference.
        timeout shortened, creates new task if existing was sleeping. timeout removed, removes tracking'''
        if timeoutable.timeout is not None:
            # there is a timeout on item
            if old_timeout is None:
                # newly created timeout, so need to add tracker
                self.create_timeout_tracker(timeoutable)
            elif id(timeoutable) not in self.timeouts_tracker:
                    # error case, if there's an old timeout there should be something in trackers.
                    #  but not terrible if it isn't there
                    self.create_timeout_tracker(timeoutable)
            elif timeoutable.timeout < old_timeout:
                # there is old timeout, only case we need to deal with is shortened timeout
                existing_task = self.timeouts_tracker[id(timeoutable)]
                if existing_task.state == TASK_STATE.WAITING:
                    # only when waiting might wake up really late so cancel and recreate
                    # don't want to disturb if in middle of event handling, plus there's no changes if
                    #   timeout was updated to before old and already handling
                    existing_task.cancel()
                    self.create_timeout_tracker(timeoutable)
        else:
            # no timeout on node
            if old_timeout is not None:
                # used to have a timeout, if it was tracked that is not needed anymore
                if id(timeoutable) in self.timeouts_tracker:
                    existing_task = self.timeouts_tracker[id(timeoutable)]
                    if existing_task.state == TASK_STATE.WAITING:
                        # only when waiting might wake up really late so cancel and recreate
                        # don't want to disturb if in middle of event handling
                        existing_task.cancel()
                    del self.timeouts_tracker[id(timeoutable)]

    async def single_node_timeout_handler(self, node:BaseType.BaseNode):
        if id(node) in self.active_node_cache:
            if node.is_active():
                await self._run_event_on_node(node, "timeout", {})

    async def single_node_timeout_close_handler(self, node:BaseType.BaseNode):
        try:
            cleaning_logger.debug(f"starting to clear out node {id(node)} {node.graph_node.id}")
            await self.close_node(node, timed_out=True)
            execution_reporting.warning(f"cleaning close node finished awaiting closing {id(node)}, sanity check is it stil inside {id(node) in self.active_node_cache}")
        except Exception as e:
            execution_reporting.warning(f"close node failed on node {id(node)}, details: {type(e)}, {e}")
            self.close_node(node, timed_out=True, emergency_remove=True)
        if id(node) in self.timeouts_tracker:
            del self.timeouts_tracker[id(node)]
        
    async def single_session_timeout_handler(self, session:SessionData.SessionData):
        gatherables = []
        if not session.is_active():
            return
        for node in session.linked_nodes:
            if node.is_active():
                gatherables.append(self._run_event_on_node(node, "timeout", {}))
        await asyncio.gather(*gatherables)

    async def single_session_timeout_close_handler(self, session:SessionData.SessionData):
        await self.close_session(session, timed_out=True)
        if id(session) in self.timeouts_tracker:
            del self.timeouts_tracker[id(session)]

    async def clean_task(self, task_period:float):
        this_cleaning = asyncio.current_task()
        cleaning_logger.info(f"clean task id <{id(this_cleaning)}><{this_cleaning}> starting, period is <{task_period}>")
        # want forever running task while handler is alive
        while True:
            i = 0
            while i < len(self._event_queue):
                task = self._event_queue[i]
                if task.done():
                    if not task.cancelled() and task.exception() is not None:
                        print(task.exception())
                    self._event_queue.pop(i)
                    i -= 1
                if i % 10 == 0:
                    await asyncio.sleep(0)
                i += 1
            await asyncio.sleep(task_period)

    def start_cleaning(self, event_loop:asyncio.AbstractEventLoop=None):
        if self.cleaning_task is None:
            event_loop = asyncio.get_event_loop() if event_loop is None else event_loop
            self.cleaning_task = event_loop.create_task(self.clean_task(task_period=3))

    def stop_cleaning(self):
        self.cleaning_task.cancel()

    def __del__(self):
        if len(self.active_node_cache) > 0:
            printing_active = ["<"+str(x)+"><"+node.graph_node.id+">" for x, node in self.active_node_cache.cache.items()]
            dialog_logger.warning(f"destrucor for handler. id'd <{id(self)}> sanity checking any memory leaks, may not be major thing" +\
                                  f"nodes left: <{printing_active}>")
