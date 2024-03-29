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

import src.BuiltinFuncs.BaseFuncs as BaseFuncs
# annotating function purposes
from src.utils.Enums import POSSIBLE_PURPOSES, CLEANING_STATE, ITEM_STATUS

import src.utils.SessionData as SessionData
# validating function data
from jsonschema import validate, ValidationError
# type annotations
import src.DialogNodes.BaseType as BaseType

import src.utils.Cache as Cache
import src.DialogNodes.CacheNodeIndex as NodeIndex

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
#TODO: refine how nodes and sessions lifetimes interact
#TODO: create modal support
#TODO: saving and loading active nodes
#TODO: maybe transition callback functions have a transition info paramter?
#TODO: should runtime be able to affect the node settings like next node to go to, callback list etc
#TODO: Templating yaml?
#TODO: go through code fine sweep for anything that could be changing data meant to be read
#TODO: during transition order is to section session which closes node which has only one set way to close every time then does transition callbacks.
#       This causes a flickering of buttons on discord menu message. Can I get that to not happen somehow? Can i get more info to close node so it can pass it to callbacks about why it's called?
#       tho at least close_node knowing why it was calle would be good for debugging
#TODO: might need add to async handle events later thing instead of awaitng notify

#NOTE: each active node will get a reference to handler. Be careful what callbacks are added as they can mess around with handler itself

class DialogHandler():
    def __init__(self, nodes:"dict[str, BaseType.BaseGraphNode]"=None, functions=None, settings = None, **kwargs) -> None:
        dialog_logger.debug(f"dialog handler being initialized, id is <{id(self)}>")
        self.graph_nodes:dict[str, BaseType.BaseGraphNode] = nodes if nodes is not None else {}
        '''dict of nodes that represent graph this handler controls. other handlers linking to same list is ok and on dev to handle.'''
        self.functions = functions if functions is not None else {}
        '''dict of functions this handler is allowed to call. other handlers linking to same list is ok and on dev to handle.'''

        self.active_node_cache = Cache.Cache(input_secondary_indices=[NodeIndex.CacheNodeIndex("event_forwarding", "event")], defualt_get_copy_rule=Cache.COPY_RULES.SHALLOW)
        '''store for all active nodes this handler is in charge of handling events on. is mapping of unique id to node object'''

        self.sessions:dict[int, SessionData.SessionData] = {}
        #TODO: not relly using the session finding dict
        self.session_finding = {}

        #TODO: still need to integrate and use these settings everywhere, especially the reading sections
        #       but before doing that probably want to think through what reporting will look like, where should reports go: dev, operator, server logs, bot logs?
        self.settings = copy.deepcopy(settings) if settings is not None else {}
        if "exception_level" not in self.settings:
            self.settings["exception_level"] = "ignore"

        self.cleaning_task = None
        self.cleaning_status = {"state":CLEANING_STATE.STOPPED, "next": None, "now": None}

        self.register_module(BaseFuncs)

        # passed in as extra settings
        for key, option in kwargs.items():
            if hasattr(self, key):
                raise Exception(f"trying to add extra attribute {key} but conflicts with existing attribute")
            setattr(self, key, option)

    '''################################################################################################
    #
    #                                   SETUP FUNCTIONS SECTION
    #
    ################################################################################################'''

    def setup_from_files(self, file_names:"list[str]" = []):
        '''override current graph with nodes in the passed in files. Raises error if nodes have double definitions in listed files
          or graph node definition badly formatted.'''
        #TODO: second pass ok and debug running
        self.graph_nodes=nodeParser.parse_files(*file_names, existing_nodes={})

    def add_nodes(self, node_list:"dict[str, BaseType.BaseGraphNode]"={}, overwrites_ok=False):
        '''add all nodes in list into handler. gives a warning on duplicates
         dev note: assumed handler is now responsible for the objects passed in'''
        #TODO: second pass ok and debug running
        for node in node_list.values():
            if node.id in self.graph_nodes:
                if overwrites_ok:
                    self.graph_nodes[node.id] = node
                else:
                    # possible exception, want to have setting for whether or not it gets thrown
                    execution_reporting.warning(f"tried adding <{node.id}>, but is duplicate. ignoring it.")
                    continue
            else:
                self.graph_nodes[node.id] = node
    
    def add_files(self, file_names:"list[str]"=[]):
        #TODO: second pass ok and debug running
        # note if trying to create a setting to ignore redifinition exceptions, this won't work since can't sort out redefinitions exceptions from rest
        nodeParser.parse_files(*file_names, existing_nodes=self.graph_nodes)

    def reload_files(self, file_names:"list[str]"=[]):
        updated_nodes = nodeParser.parse_files(*file_names, existing_nodes={})
        for k, node in updated_nodes.items():
            execution_reporting.info(f"updated/created node {node.id}")
            self.graph_nodes[k] = node

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
                func_ref = self.functions[func_name]["ref"]
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
        for node_id, graph_node in self.graph_nodes.items():
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

    '''################################################################################################
    #
    #                                   MANAGING CALLBACK FUNCTIONS SECTION
    #
    ################################################################################################'''

    def register_function(self, func, override_settings={}):
        '''register a function as allowed to use by this handler. Can override some of the function's default settings
        
        Parameters
        ---
        * func - `callable`
            function that you want handler to be able to call. Must have fields attached that hold configuration settings for how function works in handler. see callbackUtils for settings
        * override_settings -  `dict[str, Any]`
            dict holding setting name to settings this handler should override function's default ones with. currently only looks for 'allowed_sections' and 'cb_key'
            
        Return
        ---
        boolean for if function was successfully registered'''
        permitted_purposes = func.allowed_sections
        if "allowed_sections" in override_settings:
            permitted_purposes = override_settings["allowed_sections"]

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
        if cb_key in self.functions:
            # this is an exception so that developer can know as soon as possible instead of silently ignoring second one and causeing confusion 
            # why the function isn't being called
            raise Exception(f"trying to register function <{func.__name__}> with key <{cb_key}> but key already registered. " +\
                                        f"If they are different fuctions, can change key to register by. "+ \
                                        "be aware yaml has to match the key registered with")

        dialog_logger.debug(f"dialog handler id'd {id(self)} registered callback <{func}> with key <{cb_key}> {'same as default' if cb_key == func.cb_key else 'overridden'} for purposes: " +\
                            f"<{[purpose.name for purpose in permitted_purposes]}> {'same as default' if permitted_purposes == func.allowed_sections else 'overridden'}")
        #TODO: this needs upgrading if doing qualified names
        self.functions[cb_key]= {"ref": func, "permitted_purposes": permitted_purposes}
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
        '''registers function from module. module must have a variable called "dialog_func_info" that holds mapping of functions to overrides, and only those funcitons from module are registered'''
        return self.register_functions(module.dialog_func_info)

    def function_is_permitted(self, func_name:str, section:POSSIBLE_PURPOSES, escalate_errors=False):
        '''if function is registered in handler and is permitted to run in the given section of handling and transitioning

        Return
        ---
        False if function is not registered, false if registered and not permitted'''
        if func_name not in self.functions:
            execution_reporting.error(f"checking if <{func_name}> can run during phase <{section}> but it is not registered")
            if escalate_errors:
                raise Exception(f"checking if <{func_name}> can run during phase {section} but it is not registered")
            return False
        if section not in self.functions[func_name]["ref"].allowed_sections:
            execution_reporting.warn(f"checking if <{func_name}> can run during phase <{section}> but it is not allowed")
            if escalate_errors:
                raise Exception(f"checking if <{func_name}> can run during phase {section} but it is not allowed")
            return False
        return True

    '''################################################################################################
    #
    #                                   EVENTS HANDLING SECTION
    #
    ################################################################################################'''

    async def start_at(self, node_id:str, event_key:str, event):
        '''start the graph execution at the given node with given event. checks if node exists and operation is allowed.'''
        execution_reporting.info(f"dialog handler id'd <{id(self)}> starting process to start at node <{node_id}> with event <{event_key}> event deets: id <{id(event)}> type <{type(event)}> <{event}>")
        dialog_logger.debug(f"more deets for event at start at function <{event.content if hasattr(event, 'content') else 'content N/A'}>")
        if node_id not in self.graph_nodes:
            execution_reporting.warn(f"cannot start at <{node_id}>, not valid node")
            return None
        graph_node:BaseType.BaseGraphNode = self.graph_nodes[node_id]
        if not graph_node.can_start(event_key):
            execution_reporting.warn(f"cannot start at <{node_id}>, settings do not allow either starting at node or starting with event type <{event_key}>")
            return None
        
        # process session before node since the activation process binds session and currently don't have a neat written out process to bind new session
        session:typing.Union[SessionData.SessionData, None] = None
        if graph_node.starts_with_session(event_key):
            session = SessionData.SessionData()
            dialog_logger.info(f"dialog handler id'd <{id(self)}> node <{node_id}> with event <{event_key}> id <{id(event)}> start at found node starts with a session, created it. id: <{id(session)}>")
        
        # get active node, design is callbacks assume have an active node to act on, allowing reusing those for start section (and reducing functions
        #   to maintain/store) means want an active node before processing callbacks
        active_node:BaseType.BaseNode = graph_node.activate_node(session)
        # some callbacks may depend on this assignment
        active_node.assign_to_handler(self)
        dialog_logger.debug(f"dialog handler id'd <{id(self)}> node <{node_id}> with event <{event_key}> id <{id(event)}> oject type <{type(event)}> has active node now <{id(active_node)}>, running callbacks")
        # some filters may want to depend on session data, which usually gets chance to setup on transition. Startup doesn't get any other chance
        #   than running some callbacks before filters
        await self.run_event_callbacks_on_node(active_node, event_key, event, version="start")
        dialog_logger.debug(f"dialog handler id'd <{id(self)}> node <{id(active_node)}><{node_id}> with event <{event_key}> id <{id(event)}> oject type <{type(event)}> starting custom filter process")
        start_filters_result = self.run_event_filters_on_node(active_node, event_key, event, start_version=True)
        if start_filters_result:
            await self.track_active_node(active_node, event)
            execution_reporting.info(f"started active version of <{node_id}>, unique id is <{id(active_node)}>")
            if session is not None:
                session.add_node(active_node)
                self.register_session(session)

    async def notify_event(self, event_key:str, event):
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
        waiting_nodes = self.get_waiting_nodes(event_key)
        dialog_logger.debug(f"nodes waiting for event <{event_key}> are <{[str(id(x))+ ' ' +x.graph_node.id for x in waiting_nodes]}>")
        # don't use gather here, think it batches it so all nodes responding to event have to pass callbacks before any one of them go on to transitions
        # each node is mostly independent of others for each event and don't want them to wait for another node to finish
        notify_results = await asyncio.gather(*[self.run_event_on_node(node, event_key, event) for node in waiting_nodes])
        dialog_logger.debug(f"handler id'd <{id(self)}> results returned to notify method are <{notify_results}>")

    '''################################################################################################
    #
    #                                       RUNNING EVENTS SECTION
    #
    ################################################################################################'''

    async def run_event_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''processes event happening on the given node'''
        execution_reporting.debug(f"handler id'd <{id(self)}> running event <{id(event)}><{event_key}><{type(event)}> on node <{id(active_node)}><{active_node.graph_node.id}>")
        debugging_phase = "begin"
        # try: #try catch around whole event running, got tired of it being hard to trace Exceptions so removed
        debugging_phase = "filtering"
        filter_result = self.run_event_filters_on_node(active_node, event_key, event)
        debugging_phase = "filtered"
        if not filter_result:
            return
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> passed filter stage")

        debugging_phase = "running callbacks"
        await self.run_event_callbacks_on_node(active_node, event_key, event)
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> finished event callbacks")

        debugging_phase = "transitions"
        transition_result = await self.run_transitions_on_node(active_node,event_key,event)
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> finished transitions")

        # checking if should close after event, combine event schedule_close flag and what was returned fron transitions
        close_flag = active_node.graph_node.get_event_close_flags(event_key)
        should_close_node = ("node" in close_flag) or transition_result["node"]
        should_close_session = ("session" in close_flag) or transition_result["session"]
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


    def run_event_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, start_version=False):
        '''runs all custom filter callbacks for either starting at node or event for the given node and event pair. Filters are all syncronous callbacks.
        Catches and logs all errors from trying to run functions, stops going through list immediately'''
        dialog_logger.debug(f"handler id'd <{id(self)}> running event filters. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, type of event <{type(event)}> filters: <{active_node.graph_node.get_event_filters(event_key)}>")
        
        #custom event types designed to have extra addon filters, still being fleshed out as of 3.6.0
        if hasattr(event, "get_event_filters") and callable(event.get_event_filters):
            node_filters = event.get_event_filters()
            dialog_logger.debug(f"filters from custom event {node_filters}")
        else:
            node_filters = []
        
        if start_version:
            dialog_logger.debug(f"running start version of filters on node {active_node}, start filters are {active_node.graph_node.get_start_filters(event_key)}")
            node_filters.extend(active_node.graph_node.get_start_filters(event_key))
        else:
            node_filters.extend(active_node.graph_node.get_event_filters(event_key))
        execution_reporting.debug(f"custom filter list for node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}> is <{node_filters}>")

        try:
            return self.filter_list_runner(active_node, event, node_filters, purpose=POSSIBLE_PURPOSES.FILTER)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")
            return False
    

    async def run_event_callbacks_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, version:typing.Union[str, None] = None):
        '''helper that runs the list of custom callback actions of the specified version for a node event pair. Catches and logs any errors from 
        attempting to run the custom callbacks, stops going through list immediately
        
        Parameters:
        ---
        version - `str`
            "start", "close", or None. specifies which list to run: start setup for event, close callbacks, or regular for given event'''
        if version == "start":
            callbacks = active_node.graph_node.get_start_callbacks(event_key)
            execution_reporting.debug(f"running start callbacks. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        elif version == "close":
            callbacks = active_node.graph_node.get_close_callbacks()
            execution_reporting.debug(f"running closing callbacks. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        else:
            callbacks = active_node.graph_node.get_event_callbacks(event_key)
            execution_reporting.debug(f"running event callback. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, callbacks: <{callbacks}>")
        
        try:
            await self.action_list_runner(active_node, event, callbacks, POSSIBLE_PURPOSES.ACTION)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")


    def run_transition_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event) -> "list[typing.Tuple[str,list,str,list]]":
        node_transitions = active_node.graph_node.get_transitions(event_key)
        passed_transitions:list[typing.Tuple[str,list,str,list]] = []
        for transition_ind, transition in enumerate(node_transitions):
            dialog_logger.debug(f"starting checking transtion <{transition_ind}>")

            # might have just one next node, rest of format expects list of nodes so format it.
            node_name_list = transition["node_names"]
            if isinstance(transition["node_names"], str):
                node_name_list = [transition["node_names"]]

            dialog_logger.debug(f"nodes named as next in transition <{transition_ind}> are <{node_name_list}>")

            close_flag = []
            if "schedule_close" in transition:
                close_flag = transition["schedule_close"]
                if isinstance(transition["schedule_close"], str):
                    close_flag = [close_flag]

            # callbacks techinically can cause changes to stored session data though more focused on transferring data. so want to keep it clear
            # separation between filtering and callback stages to keep data cleaner
            for node_name in node_name_list:
                if node_name not in self.graph_nodes:
                    execution_reporting.warning(f"active node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}> transition won't work, goal node doesn't exist. transition indexed <{transition_ind}>")
                    continue
                    
                if "transition_filters" in transition:
                    execution_reporting.debug(f"active node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}> has transition filters {transition['transition_filters']}")
                    try:
                        filter_res = self.filter_list_runner(active_node, event, transition["transition_filters"], POSSIBLE_PURPOSES.TRANSITION_FILTER, node_name)
                        # transition_filter_helper(self, active_node, event, node_name, transition["transition_filters"])
                        if isinstance(filter_res, bool) and filter_res:
                            passed_transitions.append((node_name, transition["transition_actions"] if "transition_actions" in transition else [],
                                                        transition["session_chaining"] if "session_chaining" in transition else "end", close_flag))
                    except Exception as e:
                        execution_reporting.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}>. assuming skip")
                        dialog_logger.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}>, details {e}")
                else:
                    passed_transitions.append((node_name, transition["transition_actions"] if "transition_actions" in transition else [],
                                               transition["session_chaining"] if "session_chaining" in transition else "end", close_flag))
        return passed_transitions

    async def run_transitions_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''handles going through transition to new node (not including closing current one if needed) for one node and event pair'''

        passed_transitions = self.run_transition_filters_on_node(active_node, event_key, event)
        dialog_logger.debug(f"transitions for node <{id(active_node)}><{active_node.graph_node.id}> that passed filters are for nodes <{[x[0] for x in passed_transitions]}>, now starting transitions")

        passed_chaining_settings = set([tran[2] for tran in passed_transitions])
        if "section" in passed_chaining_settings and active_node.session is not None:
            dialog_logger.debug(f"early session sectioning to support multiple transitions. Going to close previous nodes")
            await self.clear_session_history(active_node.session)

        dialog_logger.debug(f"gathering passed transition info for node <{id(active_node)}><{active_node.graph_node.id}>")

        # first pass is just checking info
        callbacks_list:list[typing.Tuple[BaseType.BaseNode, list]] = []
        resulting_close_flags = {"node":False, "session":False}
        for passed_transition in passed_transitions:
            session = None
            if passed_transition[2] == "start" or (passed_transition[2] == "chain" and active_node.session is None):
                dialog_logger.info(f"starting session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{passed_transition[0]}>")
                #TODO: allow yaml specify timeout for sessions?
                session = SessionData.SessionData()
                self.register_session(session)
                dialog_logger.debug(f"session debugging, started new session, id is <{id(session)}>")
            elif passed_transition[2] != "end":
                session = active_node.session

            # end always has session=None
            # start always fresh session data
            # chain can have fresh session or this node's which is none or existing
            # section has this node's which is none or existing

            next_node = self.graph_nodes[passed_transition[0]].activate_node(session)
            execution_reporting.info(f"activated next node, is of graph node <{passed_transition[0]}>, id'd <{id(next_node)}>")
            if passed_transition[2] != "end" and session is not None:
                dialog_logger.info(f"adding next node to session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{passed_transition[0]}>")
                session.add_node(next_node)
                dialog_logger.info(f"session debugging, session being chained. id <{id(session)}>, adding node <{id(next_node)}><{next_node.graph_node.id}> to it, now node list is <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
            
            close_flag = passed_transition[3]
            resulting_close_flags["node"] = resulting_close_flags["node"] or ("node" in close_flag)
            resulting_close_flags["session"] = resulting_close_flags["session"] or ("session" in close_flag)
            callbacks_list.append((next_node, passed_transition[1]))

        #NOTE: for multiple passed transitions the node data could be different at the start of each transition action's call
        for callback_settings in callbacks_list:
            await self.action_list_runner(active_node, event, callback_settings[1], POSSIBLE_PURPOSES.TRANSITION_ACTION, goal_node=callback_settings[0])
            await self.track_active_node(callback_settings[0], event)
            dialog_logger.debug(f"checking session data for next node, {callback_settings[0].session}")
        return resulting_close_flags

     
    '''################################################################################################
    #
    #                   I-DONT-REALLY-HAVE-A-NAME-BUT-IT-DOESNT-FIT-ELSEWHERE SECTION
    #
    ################################################################################################'''

    async def track_active_node(self, active_node:BaseType.BaseNode, event):
        '''adds the given active node to handler's internal tracking. after this, node is fully considered being managed by this handler.
        adds node to handler's list of active nodes its currently is waiting on, does node actions for entering node, adds info about what events node
        is waiting for'''
        #TODO: fine tune id for active nodes
        dialog_logger.info(f"dialog handler id'd <{id(self)}> adding node <{id(active_node)}><{active_node.graph_node.id}> to internal tracking and running node callbacks")
        active_node.assign_to_handler(self)

        await self.action_list_runner(active_node, event, active_node.graph_node.get_callbacks(), POSSIBLE_PURPOSES.ACTION)
        
        self.active_node_cache.add(id(active_node), active_node, addition_copy_rule=Cache.COPY_RULES.ORIGINAL)
        self.notify_soonest_cleaning(active_node.timeout)

        #not adding register session cause most likely passing in new node every time, but not gauranteed unique session every new node. (even though currently that's technically not an issue)
        
        # used to have autoremoval for nodes that aren't waiting for anything, but found there might be cases where want to keep node around
        # if len(active_node.graph_node.get_events()) < 1:
        #     await self.close_node(active_node, timed_out=False)


    async def close_node(self, active_node:BaseType.BaseNode, timed_out=False, emergency_remove = False):
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
        if active_node.is_active():
            active_node.notify_closing()
        execution_reporting.info(f"closing node <{id(active_node)}><{active_node.graph_node.id}> timed out? <{timed_out}>")
        if not emergency_remove:
            await self.run_event_callbacks_on_node(active_node, "close", {"timed_out":timed_out}, version="close")

        active_node.close()
        # this section closes the session if no other nodes in it are active. causing issues with sectioning session into steps (which clears recorded nodes when going to next step)
        # if active_node.session and active_node.session is not None:
        #     session_void = True
        #     for node in active_node.session.get_linked_nodes():
        #         if node.is_active():
        #             session_void = False
        #             break
            
        #     if session_void:
        #         await self.close_session(active_node.session)
        dialog_logger.info(f"finished custom callbacks closing <{id(active_node)}><{active_node.graph_node.id}>, clearing node from internal trackers")
        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.items()}
        dialog_logger.debug(f"current state is active nodes are <{printing_active}>")
        printing_forwarding = {event:[str(x)+' '+self.active_node_cache.get(x)[0].graph_node.id for x in nodes] for event,nodes in self.active_node_cache.items(index_name="event_forwarding")}
        dialog_logger.debug(f"current state is event forwarding <{printing_forwarding}>")

        self.active_node_cache.delete(id(active_node))
        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.items()}
        dialog_logger.debug(f"after remove state is active nodes are <{printing_active}>")
        printing_forwarding = {event:[str(x)+' '+self.active_node_cache.get(x)[0].graph_node.id for x in nodes] for event,nodes in self.active_node_cache.items(index_name="event_forwarding")}
        dialog_logger.debug(f"after remove state is event forwarding <{printing_forwarding}>")

    def register_session(self, session:SessionData.SessionData):
        '''adds the given session info to handler's internal tracking for sessions'''
        if session is None:
            dialog_logger.warning(f"somehow wanting to add none session, should not happen")
            return
        session.activate()
        self.sessions[id(session)] = session
    
    async def clear_session_history(self, session:SessionData.SessionData, timed_out=False):
        for node in session.get_linked_nodes():
            if node.is_active():
                await self.close_node(node, timed_out=timed_out)
        session.clear_session_history()
    
    async def close_session(self, session:SessionData.SessionData, timed_out=False):
        if session.is_active():
            session.notify_closing()
        execution_reporting.debug(f"closing session <{id(session)}>, current nodes <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
        await self.clear_session_history(session, timed_out=timed_out)
        session.close()
        del self.sessions[id(session)]
        pass

    '''################################################################################################
    #
    #                                       FUNCTION CALLBACK HELPERS SECTION
    #
    ################################################################################################'''

    async def action_list_runner(self, active_node:BaseType.BaseNode, event, action_list, purpose: POSSIBLE_PURPOSES, goal_node=None):
        for callback in action_list:
            if isinstance(callback, str):
                await self.run_func_async(callback, purpose, active_node, event, goal_node=goal_node)
            else:
                key = list(callback.keys())[0]
                value = callback[key]
                await self.run_func_async(key, purpose, active_node, event, goal_node=goal_node, values=value)

    def filter_list_runner(self, active_node:BaseType.BaseNode, event, filter_list, purpose:POSSIBLE_PURPOSES, goal_node=None, operator="and"):
        '''helper for running a section of filter callbacks. handles nested lists and can apply and/or logic to results from running each function.'''
        for filter in filter_list:
            # dialog_logger.debug(f"testing recursive helper, at filter {filter} in list for node <{id(active_node)}><{active_node.graph_node.id}>")
            if isinstance(filter, str):
                filter_run_result = self.run_func(filter, purpose, active_node, event, goal_node=goal_node)
            else:
                # is a dict representing function call with arguments or nested operator, should only have one key
                key = list(filter.keys())[0]
                value = filter[key]
                if key in ["and", "or"]:
                    filter_run_result = self.filter_list_runner(active_node, event, value, purpose, goal_node, operator=key)
                else:
                    # argument in vlaue is expected to be one object. a list, a dict, a string etc
                    filter_run_result = self.run_func(key, purpose, active_node, event, goal_node=goal_node, values=value)
            # early break because not possible to change result with rest of list
            if operator == "and" and not filter_run_result:
                # dialog_logger.debug(f"at filter {filter} in list for node <{id(active_node)}><{active_node.graph_node.id}>, returning False")
                return False
            if operator == "or" and filter_run_result:
                # dialog_logger.debug(f"at filter {filter} in list for node <{id(active_node)}><{active_node.graph_node.id}>, returning True")
                return True
        # end of for loop, means faild to find early break point
        if operator == "and":
            # dialog_logger.debug(f"<{id(active_node)}><{active_node.graph_node.id}> got through sub?list, returning True")
            return True
        if operator == "or":
            # dialog_logger.debug(f"<{id(active_node)}><{active_node.graph_node.id}> got through sub?list, returning False")
            return False

    def format_parameters(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, goal_node:typing.Union[BaseType.BaseNode, str] = None, values = None):
        '''
        Takes information that is meant to be passed to custom filter/callback functions and gets the parameters in the right order to be passed.
        parameters will be passed in this order: the active node instance, the event that happened to node, and next two are situational.
        if function cal be called in transition section, generally the order is next node then any extra arguments, unless function requires extra arguments but can be called in transition or not,
        then last two are swapped.

        PreReq
        ---
        function passed in is being called for one of its intended purposes
        '''
        # dialog_logger.debug(f"starting formatting parameters for function call. passed in: purpose <{purpose}>, a, e, g, v: <{id(active_node)}><{active_node.graph_node.id}>, <{event}>, <{goal_node}>, <{values}>")
        func_ref = self.functions[func_name]["ref"]
        intended_purposes = [x in func_ref.allowed_sections for x in [POSSIBLE_PURPOSES.FILTER,POSSIBLE_PURPOSES.ACTION,POSSIBLE_PURPOSES.TRANSITION_FILTER,POSSIBLE_PURPOSES.TRANSITION_ACTION]]
        cross_transtion = (intended_purposes[2] or intended_purposes[3]) and (intended_purposes[0] or intended_purposes[1])

        args_list = [active_node, event]
        if cross_transtion and func_ref.has_parameter == "always":
            # if can do transition and non-transition, and function has four parameters and only one is optional
            # if can do both transition and non-transitional, goal node parameter has to be optional
            # in this case only having one optional parameter means the arguments to the function is required.
            # ordering is values are passed last, so if that is required, then it and goal need to be swapped
            if values is None:
                raise Exception(f"missing arguments to pass to function {func_name}")
            args_list.append(values)
            if purpose in [POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION]:
                if goal_node is None:
                    raise Exception(f"trying to call {func_name} but is missing required goal node")
                args_list.append(goal_node)
            else:
                args_list.append(None)
            dialog_logger.debug(f"Dialog handler id'd <{id(self)}> ordering parameters for running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>. order is a e v g. details: {args_list}")
            return args_list
        
        # cross_transition and either optional or None
        # or not cross transition, any parameter option
        # all of these cases parameters come after goal node if it is there
        
        # try to fill in goal node
        if purpose in [POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION]:
            # function is getting called for handling transition
            if goal_node is None:
                raise Exception(f"trying to call {func_name} for a transition but are missing goal node")
            args_list.append(goal_node)
        elif cross_transtion:
            # if calling for non-transitional, function can still be one that accepts both, so thats why there's this if check
            # if function can take both goal node field is optional
            args_list.append(None)

        # handle adding parameters
        if func_ref.has_parameter is not None:
            if func_ref.has_parameter == "always" and values is None:
                raise Exception(f"trying to call {func_name} for a transition but are missing parameters to pass to it")
            args_list.append(values)
        elif values is not None:
            execution_reporting.warning(f"calling {func_name}, have extra value for function parameters, discarding")
            
        dialog_logger.debug(f"Dialog handler id'd <{id(self)}> odering parameters for running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>. order is a e g? v?. details: {args_list}")
        return args_list

    #NOTE: keep this function in sync with synchronous version
    async def run_func_async(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, goal_node:typing.Union[BaseType.BaseNode, str] = None, values= None):
        '''helper for running a dialog callback that could be async. awaits result if asynchronous. func_name and purpose is for checking information on formatting, rest are values that dialog callbacks need'''
        if not self.function_is_permitted(func_name, purpose):
            dialog_logger.debug(f"Dialog handler id'd <{id(self)}> tried running async function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>, not allowed.")
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                # filter functions, wether transtion or not, expect bool returns. assume not allowed (function not listed in handler, or running for wrong purpose) smeans failed filter
                return False
            else:
                return None
        func_ref = self.functions[func_name]["ref"]
        dialog_logger.debug(f"Dialog handler id'd <{id(self)}> starting running async function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>")
        if inspect.iscoroutinefunction(func_ref):
            return await func_ref(*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
        return func_ref(*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
    

    #NOTE: keep this function in sync with asynchronous version
    def run_func(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, goal_node:typing.Union[BaseType.BaseNode, str] = None, values= None):
        '''helper for running a dialog callback. func_name and purpose is for checking information on formatting, rest are values that dialog callbacks need'''
        if not self.function_is_permitted(func_name, purpose):
            dialog_logger.debug(f"Dialog handler id'd <{id(self)}> tried running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>, not allowed")
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                # filter functions, wether transtion or not, expect bool returns. assume not allowed (function not listed in handler, or running for wrong purpose) means failed filter
                return False
            else:
                return None
        dialog_logger.debug(f"Dialog handler id'd <{id(self)}> starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>")
        func_ref = self.functions[func_name]["ref"]
        return func_ref(*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
    
    '''################################################################################################
    #
    #                                       MANAGING HANDLER DATA SECTION
    #
    ################################################################################################'''

    def get_waiting_nodes(self, event_key):
        '''gets list of active nodes waiting for certain event from handler'''
        return self.active_node_cache.get(event_key, index_name="event_forwarding", default=set())
    
    '''################################################################################################
    #
    #                                       CLEANING OUT NODES SECTION
    #
    ################################################################################################'''

    # NOTE: This task is not built for canceling. canceling can cause stopping in middle of custom cleanup methods, no tracking currently to prevent double calls to methods.
    async def clean_task(self, delay:float):
        this_cleaning = asyncio.current_task()
        cleaning_logger.info(f"clean task id <{id(this_cleaning)}><{this_cleaning}> starting, initial delay is <{delay}>")
        await asyncio.sleep(delay)
        cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> initial sleep done, checking if looping. current status {self.cleaning_status} and task {this_cleaning}")
        while self.cleaning_status["state"] in [CLEANING_STATE.STARTING, CLEANING_STATE.RUNNING]:
            cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> is going through a loop current state {self.cleaning_status}")
            if this_cleaning == self.cleaning_task:
                self.cleaning_status["state"] = CLEANING_STATE.RUNNING
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> inital startup changed state to running {self.cleaning_status}")
            starttime = datetime.utcnow()
            
            cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> getting timed out items. current state {self.cleaning_status}")
            timed_out_nodes, timed_out_sessions, next_time = self.get_timed_out_info()
            if this_cleaning == self.cleaning_task:
                self.cleaning_status["now"] = self.cleaning_status["next"]
                self.cleaning_status["next"] = next_time
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> changed next time state {self.cleaning_status}")

            if next_time is None:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found time for next clean is none, no further cleaning possible current state {self.cleaning_status}")
            else:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found next round is at {next_time}, {(next_time - starttime).total_seconds()} from now")
            
            try:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> doing actual node pruning current state {self.cleaning_status}")
                ## cleaning option 1 ~~~~~~~~~~v
                # if this_cleaning == self.cleaning_task and next_time is not None:
                #     await asyncio.wait_for(self.clean(timed_out_nodes, timed_out_sessions), timeout = (next_time-datetime.utcnow()).total_seconds())
                # else:
                #     # let any other run of this task that is lagging and not main to just silently finish. hopefully to catch last few nodes
                #     await self.clean(timed_out_nodes, timed_out_sessions)
                ## cleaning option 1 ~~~~~~~~~~^
                ## cleaning option 2 ~~~~~~~~~~v
                await self.clean(timed_out_nodes, timed_out_sessions, next_time=next_time, this_cleaning=this_cleaning)
                ## cleaning option 2 ~~~~~~~~~~^
            ## cleaning option 1 ~~~~~~~~~~v
            # except asyncio.TimeoutError:
            #     # only possible to get here if already the main task
            #     cleaning_logger.debug(f"cleaning task {id(this_cleaning)} found clean is going long past next clean so starting clean before finishing.")
            #     cleaning_logger.debug(f"same position as above, current active nodes: {[str(id(x))+' ' + x.graph_node.id for x in self.active_node_cache.values()]}")
            #     self.cleaning_status["state"] = CLEANING_STATE.STOPPING
            #     # starts a new task for cleaning, get the new timed out nodes asap
            #     self.start_cleaning()
            #     # but also finish this round's cleaning to make sure all nodes are covered. 
            #     # and make sure rest of method is protected for multiple concurrent tasks
            #     await self.clean(timed_out_nodes, timed_out_sessions)
            ## cleaning option 1 ~~~~~~~~~~^
            # except asyncio.CancelledError:
            #     raise
            except Exception as e:
                # last stop catch for exceptions just in case, otherwise will not be caught and aysncio will complain of unhandled exceptions
                if this_cleaning == self.cleaning_task:
                    execution_reporting.warning(f"error, abnormal state for handler's cleaning functions, cleaning is now stopped")
                    cleaning_logger.warning(f"handler id {id(self)} cleaning task id <{id(this_cleaning)}> at time {starttime} failed. details: {type(e)} {e}")
                    self.cleaning_status["state"] = CLEANING_STATE.STOPPED
                    self.cleaning_status["now"] = None
                    self.cleaning_status["next"] = None
                    cleaning_logger.warning(f"cleaning task id <{id(this_cleaning)}> at failure changed state to stopped {self.cleaning_status}")
                return
            
            # the task executing at this point may be one in handler or old one that started but ran over time but stayed running to make sure
            # nodes it found are cleaned
            if self.cleaning_status["state"] in [CLEANING_STATE.STOPPING, CLEANING_STATE.STOPPED]:
                # if cleaning is trying to stop, don't really want to loop for another clean. doesn't matter which task. so go to wrap up section
                break
            elif this_cleaning == self.cleaning_task:
                # only want to consider looping on main task, other ones are are only meant to finish current clean to make sure nodes are cleaned up 
                #       in case the task restarts can't get to them
                if next_time is None:
                    # cleans not needed currently so mark it differently from stopped to know its ok to auto start them up again
                    cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found time for next clean is none, no further cleaning possible current state {self.cleaning_status}")
                    self.cleaning_status["state"] = CLEANING_STATE.PAUSED
                    self.cleaning_status["now"] = None
                    self.cleaning_status["next"] = None
                    return

                next_sleep_secs = max(0, (next_time - datetime.utcnow()).total_seconds())
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> last step of one round of cleaning, setting sleep time and waiting. status is {self.cleaning_status}, duration is {next_sleep_secs}")
                await asyncio.sleep(next_sleep_secs)
            else:
                # if not main task only wanted to finish clean, so go to wrap up section, technically could exit just here
                break

        #after loops wrap up section. updating status if supposed to
        cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> finished loops current state {self.cleaning_status}")
        if this_cleaning == self.cleaning_task:
            self.cleaning_status["state"] = CLEANING_STATE.STOPPED
            self.cleaning_status["now"] = None
            self.cleaning_status["next"] = None
            cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> end of task changed state to stopped {self.cleaning_status}")


    def notify_soonest_cleaning(self, next_clean_time:datetime):
        if self.cleaning_status["state"] in [CLEANING_STATE.STOPPED, CLEANING_STATE.STOPPING] or next_clean_time is None:
            return
        if self.cleaning_status["next"] is None or next_clean_time < self.cleaning_status["next"]:
            dialog_logger.debug(f"handler notify soonest found the next clean time needed is sooner than next time the task has, starting new task")
            self.stop_cleaning()
            self.start_cleaning()

    def get_timed_out_info(self) -> 'tuple[list[BaseType.BaseNode],list[SessionData.SessionData],typing.Union[datetime,None]]':
        now = datetime.utcnow()
        # TODO: future performance upgrade: all this sorting can probably be skipped with a min-heap structure. at this point too lazy to implement
        next_soonest_timestamp = None
        timed_out_nodes = []
        for node_key, active_node in self.active_node_cache.items():
            # every node will have timeout, it might be valid teime or a None
            if active_node.timeout is not None:
                if active_node.timeout <= now:
                    cleaning_logger.debug(f"found node <{id(active_node)}><{active_node.graph_node.id}> has timed out")
                    timed_out_nodes.append(active_node)
                else:
                    if next_soonest_timestamp is None or active_node.timeout < next_soonest_timestamp:
                        next_soonest_timestamp = active_node.timeout

        timed_out_sessions = []
        for session in self.sessions.values():
            cleaning_logger.debug(f"checking session <{id(session)}> timeout is <{session.timeout}> and should be cleaned <{session.timeout < now}>")
            if session is None:
                cleaning_logger.warning(f"found handler has recorded a session that is in an invalid state. It is for some reason None")
            elif session.timeout is not None:
                if session.timeout <= now:
                    timed_out_sessions.append(session)
                else:
                    if next_soonest_timestamp is None or session.timeout > next_soonest_timestamp:
                        next_soonest_timestamp = session.timeout
        return timed_out_nodes, timed_out_sessions, next_soonest_timestamp


    #NOTE: FOR CLEANING ALWAYS BE ON CAUTIOUS SIDE AND DO TRY EXCEPTS ESPECIALLY FOR CUSTOM HANDLING. maybe should throw out some data if that happens?
    async def clean(self, timed_out_nodes:"list[BaseType.BaseNode]", timed_out_sessions:"list[SessionData.SessionData]", next_time:typing.Union[datetime,None]=None, this_cleaning:typing.Union[asyncio.Task,None]=None):
        cleaning_logger.debug("doing cleaning action. handler id <%s> task id <%s>", id(self), id(asyncio.current_task()) if asyncio.current_task() else "N/A")
        # clean out old data from internal stores
        #TODO: more defenses and handling for exceptions
        for node in timed_out_nodes:
            try:
                # assuming if not active, some clean task busy cleaning. hopefully doesn't mess anything up
                if id(node) in self.active_node_cache and node.is_active():
                    cleaning_logger.debug(f"starting to clear out node {id(node)} {node.graph_node.id}")
                    await self.close_node(node, timed_out=True)
                    execution_reporting.warning(f"cleaning close node finished awaiting closing {id(node)}, sanity check is it stil inside {id(node) in self.active_node_cache}")
            except Exception as e:
                execution_reporting.warning(f"close node failed on node {id(node)}, details: {type(e)}, {e}")
                self.close_node(node, timed_out=True, emergency_remove=True)
            ## cleaning option 2: ~~~~~~~~~v
            if this_cleaning is not None and self.cleaning_task is this_cleaning and next_time is not None and next_time < datetime.utcnow() and\
                    self.cleaning_status["state"] not in [CLEANING_STATE.STOPPED, CLEANING_STATE.STOPPING]:
                cleaning_logger.debug(f"cleaning task {id(this_cleaning)} found clean is going long past next clean so starting clean before finishing.")
                cleaning_logger.debug(f"same position as above,  current active nodes: {[str(id(x))+' ' + x.graph_node.id for x in self.active_node_cache.values()]}")
                self.stop_cleaning()
                # starts a new task for cleaning, get the new timed out nodes asap
                self.start_cleaning()
            ## cleaning option 2: ~~~~~~~~~^
    
        for session in timed_out_sessions:
            try:
                if id(session) in self.sessions and session.is_active():
                    await self.close_session(session, timed_out=True)
            except Exception as e:
                execution_reporting.warning(f"close session failed on session {id(session)}, just going to ignore it for now")
            ## cleaning option 2: ~~~~~~~~~v
            if this_cleaning is not None and self.cleaning_task is this_cleaning and next_time is not None and next_time < datetime.utcnow() and\
                    self.cleaning_status["state"] not in [CLEANING_STATE.STOPPED, CLEANING_STATE.STOPPING]:
                cleaning_logger.debug(f"cleaning task {id(this_cleaning)} found clean is going long past next clean so starting clean before finishing.")
                self.stop_cleaning()
                # starts a new task for cleaning, get the new timed out nodes asap
                self.start_cleaning()
            ## cleaning option 2: ~~~~~~~~~^


    def start_cleaning(self, event_loop:asyncio.AbstractEventLoop=None):
        event_loop = asyncio.get_event_loop() if event_loop is None else event_loop
        'method to get the repeating cleaning task to start'
        if self.cleaning_status["state"] in [CLEANING_STATE.RUNNING, CLEANING_STATE.STARTING]:
            return False
        self.cleaning_task = event_loop.create_task(self.clean_task(delay=0))
        self.cleaning_status["state"] = CLEANING_STATE.STARTING
        self.cleaning_status["next"] = datetime.utcnow()
        cleaning_logger.info(f"starting cleaning. handler id <{id(self)}> task id <{id(self.cleaning_task)}>, <{self.cleaning_task}>")
        return True


    def stop_cleaning(self):
        cleaning_logger.info("stopping cleaning. handler id <%s> task id <%s>", id(self), id(self.cleaning_task))
        if self.cleaning_status["state"] in [CLEANING_STATE.STOPPING, CLEANING_STATE.STOPPED]:
            return False
        # res = self.cleaning_task.cancel()
        # cleaning_logger.debug(f"result from canceling attempt, {res}")
        self.cleaning_status["state"] = CLEANING_STATE.STOPPING
        cleaning_logger.debug(f"end of handler stopping method status {self.cleaning_status}, {self.cleaning_task}")
        return True


    def __del__(self):
        if len(self.sessions) > 0 or len(self.active_node_cache) > 0:
            dialog_logger.warning(f"destrucor for handler. id'd <{id(self)}> sanity checking any memory leaks, may not be major thing" +\
                                  f"sessions left: <{self.sessions}>, nodes left: <{self.active_node_cache.items()}>")

