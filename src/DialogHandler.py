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
# validating function data
from jsonschema import validate, ValidationError
# exception catch with stack trace
import traceback

import src.DialogNodeParsing as nodeParser
import src.DialogNodes.BaseType as BaseType
import src.BuiltinFuncs.BaseFuncs as BaseFuncs
import src.DialogEvents.ExceptionEvent as ExceptionEvent

import src.utils.CallbackUtils as CbUtils
# annotating function purposes
from src.utils.Enums import POSSIBLE_PURPOSES, CLEANING_STATE, ITEM_STATUS, TASK_STATE
import src.utils.SessionData as SessionData
import src.utils.ValidationUtils as ValidationUtils
import src.utils.Cache as Cache
import src.utils.HandlerTasks as HandlerTasks
import src.utils.TimeString as TimeString
import src.utils.SectionUtils as SectionUtils


dev_log = logging.getLogger('Dev-Handler-Reporting')
logHelper.use_default_setup(dev_log)
dev_log.setLevel(logging.INFO)
#Debug is alllll the details of current state

#cleaning is probably going to get really spammy so putting that in its own separate one to make debugging easier
cleaning_logger = logging.getLogger("Dialog Cleaning")
logHelper.use_default_setup(cleaning_logger)
cleaning_logger.setLevel(logging.INFO)

exec_log = logging.getLogger('Handler Reporting')
logHelper.use_default_setup(exec_log)
exec_log.setLevel(logging.DEBUG)

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

# Thoughts:
#   sapwning multiple active nodes of same graph node, transitions assume different graph nodes
#   game (send dms that each player selects action on to each person, ie warewolf, mafia) might use above case.
#       probably more useful than at beginning spawing one for everyone and syncing it to have main game turn spawn separate nodes asking each player for their turn actions
#   local broad casting event to subset
# tracking node execution progress

class HandlerSettings:
    def __init__(self, log_level="warning", strict_event_order=False, task_age:str="5m") -> None:
        self.log_level = logging.WARNING
        if log_level == "debug":
            self.log_level = logging.DEBUG
        elif log_level == "info":
            self.log_level = logging.INFO
        elif log_level == "error":
            self.log_level = logging.ERROR

        self.strict_event_order = strict_event_order
        self.task_age = TimeString.string_to_timedelta(task_age)
        # settings below still experimental
        self.timeout_cut = False
        '''EXPERIMENTAL
        ---
        if timeout gets to cut event handling line'''

class RunNodeEventOutput:
    def __init__(self, close_session=None) -> None:
        '''None means not specified or at a point that it doesn't matter. False is did not say to close, True is need to close'''
        self.close_session=close_session

class DialogHandler():
    NON_BROADCAST_EVENTS = ["timeout", "node_error", "node_warning"]
    def __init__(self, graph_nodes:"typing.Optional[dict[str, BaseType.BaseGraphNode]]"=None, functions=None, settings:HandlerSettings=None, pass_to_callbacks=None, **kwargs) -> None:
        dev_log.info(f"dialog handler being initialized, id is <{id(self)}>")
        self.graph_node_indexer = Cache.MultiIndexer(
                cache=graph_nodes,
                input_secondary_indices=[
                    Cache.FieldValueIndex("type", keys_value_finder=lambda x: [x.TYPE]),
                    Cache.FieldValueIndex("functions", keys_value_finder=lambda x: [x.TYPE]) #TODO: this doesn't work as intended, fix once I figure out functions
                ]
        )
        '''maps the string node id from yaml to graph node object.'''
        dev_log.debug(f"dialog handler <{id(self)}> initializing with GraphNode cache <{id(self.graph_node_indexer.cache)}> with <{len(self.graph_node_indexer.cache)}> nodes registered")
        dev_log.debug(f"loaded nodes' names are {self.graph_node_indexer.cache.keys()}")

        self.functions_cache = Cache.MultiIndexer(cache=functions, input_secondary_indices=[
                Cache.FieldValueIndex("sections", keys_value_finder=lambda x: x["permitted_purposes"])
            ]
        )
        '''store of functions this handler is allowed to call. other handlers linking to same list is ok and on dev to handle.
        maps function reference name to dict of function reference and other overidden settings'''
        dev_log.debug(f"dialog handler <{id(self)}> initializing with function cache <{id(self.functions_cache.cache)}> with <{len(self.functions_cache.cache)}> functions registered")
        dev_log.debug(f"loaded functions' names are {self.functions_cache.cache.keys()}")

        self.active_node_cache = Cache.MultiIndexer(
                input_secondary_indices=[
                    Cache.FieldValueIndex("graph_node", keys_value_finder=lambda x: [x.graph_node.id]),
                    Cache.FieldValueIndex("event_forwarding", keys_value_finder=lambda x: [event_type for event_type in x.graph_node.events.keys() if event_type not in DialogHandler.NON_BROADCAST_EVENTS]),
                    Cache.ObjContainsFieldIndex("has_session", keys_value_finder=lambda x: [x.session])
                ]
        )
        '''store for all active nodes this handler is in charge of handling events on. is mapping of unique id to a dictionary holding active node object and handler data for it'''

        self.advanced_event_queue = Cache.MultiIndexer(
            input_secondary_indices=[
                Cache.FieldValueIndex("task_type", keys_value_finder=lambda x: [x.type]),
                Cache.FieldValueIndex("session_id", keys_value_finder=lambda x: [self.get_session_key(x.session)] if x.type == "SessionEventTask" else []),
                Cache.FieldValueIndex("node_id", keys_value_finder=lambda x: [self.get_active_node_key(x.active_node)] if x.type == "NodeEventTask" else []),
                Cache.FieldValueIndex("session_waiters", keys_value_finder=lambda x: [self.get_session_key(x.timeoutable)] if x.type == "TimeoutWaiter" and not issubclass(x.timeoutable.__class__, BaseType.BaseNode) else []),
                Cache.FieldValueIndex("node_waiters", keys_value_finder=lambda x: [self.get_active_node_key(x.timeoutable)] if x.type == "TimeoutWaiter" and issubclass(x.timeoutable.__class__, BaseType.BaseNode) else []),
                Cache.FieldValueIndex("session_timeouts", keys_value_finder=lambda x: [self.get_session_key(x.timeoutable)] if x.type == "SessionTimeoutTask" else []),
                Cache.FieldValueIndex("node_timeouts", keys_value_finder=lambda x: [self.get_active_node_key(x.timeoutable)] if x.type == "NodeTimeoutTask" else [])
            ]
        )
        '''consolidated list of tasks to do by handler'''
        self.settings = settings if settings is not None else HandlerSettings()

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
                    exec_log.warning(f"tried adding <{node.id}>, but is duplicate. ignoring it.")
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
            exec_log.info(f"updated/created node {node.id}")
            self.graph_node_indexer.set_item(k, node)

    def final_validate(self):
        #TODO: maybe clean up and split so this can do minimal work on new nodes? or maybe just wait until someone adds all nodes?
        #TODO: smarter caching of what is validated

        def validate_function_list(function_section_info:ValidationUtils.FunctionSectionInfo):
            func_list = function_section_info.function_list
            node_id = function_section_info.node_id
            purpose = function_section_info.purpose
            string_rep = function_section_info.section_name
            event_type = function_section_info.event_type
            for callback in func_list:
                if type(callback) is str:
                    func_name = callback
                    args = None
                elif issubclass(callback.__class__, SectionUtils.SubSection):
                    if isinstance(callback, SectionUtils.IfSubSection):
                        validate_function_list(ValidationUtils.FunctionSectionInfo(callback.filters, node_id, POSSIBLE_PURPOSES.FILTER, string_rep+" filters for if statement", event_type=event_type))
                        validate_function_list(ValidationUtils.FunctionSectionInfo(callback.actions, node_id, purpose, string_rep+" actions for if statement", event_type=event_type))
                    elif issubclass(callback.__class__, SectionUtils.LogicOpSubSection):
                        validate_function_list(ValidationUtils.FunctionSectionInfo(callback.callbacks, node_id, purpose, string_rep, event_type=event_type))
                    continue
                else:
                    func_name = list(callback.keys())[0]
                    args = callback[func_name]
                
                if not self.function_is_permitted(func_name, purpose):
                    raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep} but isn't allowed to run there")
                # function has to exist at this point because the check checks for that
                func_ref = self.functions_cache.get(func_name)[0]["ref"]
                # version alpha 3.8 removing checking if missing arguments since arguments can be added/provided during runtime so don't have a complete set just by looking at yaml
                #   this version added the override checks to a bunch of callbacks after adding section data in previous changes
                # if func_ref.has_parameter == "always" and args is None:
                #     raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep}, missing required arguments")
                # elif func_ref.has_parameter is None and args is not None:
                #     raise Exception(f"Exception validating node <{node_id}>, function <{func_name}> is listed in {string_rep}, function not meant to take arguments, extra values passed")
                
                if args is not None:
                    # if there are args, try to make sure they fit definitions
                    # args provided at runtime aren't checked
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
        for node_id in self.graph_node_indexer.cache:
            graph_node:BaseType.BaseGraphNode = self.graph_node_indexer.get(node_id)[0]
            next_nodes, function_sections_info = graph_node.get_validation_info()
            for function_section in function_sections_info:
                validate_function_list(function_section)
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
            exec_log.warning(f"dialog handler tried registering a function <{func.__name__}> that does not have any permitted sections")
            return False
        if func == self.register_function:
            exec_log.warning("dialog handler tried registering own registration function, dropping for security reasions")
            return False

        cb_key = func.cb_key
        if "cb_key" in override_settings:
            exec_log.warning(f"doing manual override to register function with key <{override_settings['cb_key']}> instead of usual <{cb_key}>")
            cb_key = override_settings["cb_key"]
        if cb_key in self.functions_cache:
            # this is an exception so that developer can know as soon as possible instead of silently ignoring second one and causeing confusion 
            # why the function isn't being called
            raise Exception(f"trying to register function <{func.__name__}> with key <{cb_key}> but key already registered. " +\
                                        f"If trying to register a different function than what is registered already, change the key you are registering with. "+ \
                                        "Be aware yaml has to match the key registered with")

        dev_log.debug(f"handler id'd {id(self)} registered callback <{func}> with key <{cb_key}> {'same as default,' if cb_key == func.cb_key else 'overridden,'} for purposes: " +\
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
            exec_log.error(f"checking if <{func_key}> can run during phase <{purpose}> but it is not registered")
            if escalate_errors:
                raise Exception(f"checking if <{func_key}> can run during phase {purpose} but it is not registered")
            return False
        if purpose not in self.functions_cache.get_ref(func_key)["permitted_purposes"]:
            # note, not accessing function.allowed_sections because this field contains overridden values from registering
            exec_log.warn(f"checking if <{func_key}> can run during phase <{purpose}> but it is not allowed")
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
        exec_log.info(f"dialog handler id'd <{id(self)}> starting process to start at node <{node_id}> with event <{id(event)}><{event_key}> event deets: type <{type(event)}> <{event}>")
        try:
            dev_log.debug(f"more deets for event at start at function <{vars(event)}>")
        except Exception as e:
            dev_log.debug(f"attempt to debug output more info about event at start of start_at failed")
            dev_log.debug(f"<{event.content if hasattr(event, 'content') else 'content N/A'}>")

        if node_id not in self.graph_node_indexer:
            exec_log.warn(f"cannot start at <{node_id}>, not valid node")
            return None
        graph_node:BaseType.BaseGraphNode = self.graph_node_indexer.get_ref(node_id)
        if not graph_node.is_graph_start(event_key):
            exec_log.warn(f"cannot start at <{node_id}>, settings do not allow either starting at node or starting with event type <{event_key}>")
            return None
        
        # process session before node since the activation process binds session and currently don't have a neat written out process to bind new session
        session:typing.Optional[SessionData.SessionData] = None
        if graph_node.graph_starts_with_session(event_key):
            default_session_duration = graph_node.get_graph_start_session_TTL(event_key)
            if default_session_duration is not None:
                session = SessionData.SessionData(timeout_duration=timedelta(seconds=default_session_duration))
            else:
                session = SessionData.SessionData()
            dev_log.info(f"dialog handler id'd <{id(self)}> node <{node_id}> with event <{id(event)}><{event_key}> start at found node starts with a session, created it. id: <{self.get_session_key(session)}> timeout <{session.timeout}>")
        
        # get active node at this graph node.
        #   design of callbacks is they assume they have an active node to act on. Allowing reusing those for start section (and reducing functions
        #   to maintain/store) means want an active node before processing callbacks
        active_node:BaseType.BaseNode = graph_node.activate_node(session)
        if session is not None:
            # feels more right to set up session to mirror state of node (knowing of each other) before callbacks happen on them
            # does mean circular reference to clean up
            session.add_node(active_node)
        dev_log.debug(f"dialog handler id'd <{id(self)}> node <{node_id}> event <{id(event)}><{event_key}> start_at created active node <{self.get_active_node_key(active_node)}>, running callbacks")
        # some filters may want to depend on session data, which usually gets chance to setup on transition. Startup doesn't get any other chance
        #   than running some callbacks before filters
        # also other sections track timeouts for node and session and various other changes when calling actions, but it doesn't matter here since these haven't been tracked
        #   yet so nothing depends on detecting changes
        try:
            await self._run_actions_on_node(active_node, event_key, event, version="start")
            dev_log.debug(f"dialog handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{node_id}> event <{id(event)}><{event_key}> starting custom filter process")
            start_filters_result = self._run_filters_on_node(active_node, event_key, event, version="start")
            dev_log.debug(f"dialog handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{node_id}> event <{id(event)}><{event_key}> start_at finished filter process. passed? <{start_filters_result}>")
        except Exception as e:
            start_filters_result = False
        if not start_filters_result:
            if session is not None:
                # there's a circular reference by design, break it if it was created and node failed filters so garbage collector can get it
                session.clear_session_history()
            return None
        dev_log.debug(f"dialog handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{node_id}> event <{id(event)}><{event_key}> start_at moving to doing node actions and tracking")
        await self._track_new_active_node(active_node, event)
        exec_log.info(f"started active version of <{node_id}>, unique id is <{self.get_active_node_key(active_node)}>")

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
        task = self._create_handle_event_task(event_type=event_key, event=event)
        await task

    def notify_event(self, event_key, event):
        return self._create_handle_event_task(event_type=event_key, event=event)

    '''#############################################################################################
    ################################################################################################
    ####                                       RUNNING EVENTS SECTION
    ################################################################################################
    ################################################################################################'''

    async def _run_event_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''processes event happening on the given node'''
        exec_log.debug(f"handler id'd <{id(self)}> running event <{id(event)}><{event_key}><{type(event)}> on node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}>")
        if active_node.status == ITEM_STATUS.CLOSED:
            # node already closed. that is considered done so just return. likely this was because of a scheduled event but during running a previous event closed it. not always error.
            return RunNodeEventOutput()
        #TODO: custom exception handling could be expanded depending on use
        debugging_phase = "event_filters"
        # try: #try catch around whole event running, got tired of it being hard to trace Exceptions so removed
        filter_result = self._run_filters_on_node(active_node, event_key, event)
        if not filter_result:
            exec_log.info(f"node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> failed filter stage")
            return RunNodeEventOutput()
        dev_log.debug(f"node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> passed filter stage")

        try:
            debugging_phase = "event_actions"
            callback_close_commands = await self._run_actions_on_node(active_node, event_key, event)
            dev_log.debug(f"node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> finished event callbacks")

            debugging_phase = "event_transitions"
            transition_result = await self._run_transitions_on_node(active_node, event_key, event)
            dev_log.debug(f"node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> finished transitions")
        except Exception as e:
            exec_log.warning(f"failed to handle event <{event_key}> <{id(event)}> on node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> at stage {debugging_phase}")
            print(traceback.format_exc())
            return await self._run_event_on_node(active_node=active_node, event_key="node_error", event=ExceptionEvent.SimpleExceptionEvent(event=event, exception=e, section=debugging_phase))

        # checking if should close after event, combine event schedule_close flag and what was returned fron transitions
        close_flag = active_node.graph_node.get_event_close_flags(event_key)
        #TODO: double check how want to combine these
        should_close_node = ("node" in close_flag) or transition_result["close_node"] or callback_close_commands["close_node"]
        should_close_session = ("session" in close_flag) or transition_result["close_session"] or callback_close_commands["close_session"]
        if should_close_node and active_node.is_active():
            debugging_phase = "closing"
            await self.close_node(active_node, timed_out=event_key == "timeout")

        if should_close_session and active_node.session is not None:
            return RunNodeEventOutput(close_session=should_close_session)
        # except Exception as e:
        #     execution_reporting.warning(f"failed to handle event on node at stage {debugging_phase}")
        #     exc_type, exc_obj, exc_tb = sys.exc_info()
        #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #     print(exc_type, fname, exc_tb.tb_lineno)
        #     dialog_logger.info(f"exception on handling event on node <{self.get_active_node_key(active_node)}> node details: <{vars(active_node)}> exception:<{e}>")

    def _run_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, version:typing.Union[str, None] = None):
        '''runs all custom filter callbacks for either starting at node with given event or for the given node and event pair. Filters are all syncronous callbacks.
        Catches and logs all errors from trying to run functions, stops going through list immediately
        
        Parameters:
        ---
        version - `str`
            "start", or None. specifies which list to run: starting graph at this node filters, or regular for given event'''
        dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}>, running event filters.  type of event <{type(event)}>")
        
        if version == "start":
            dev_log.debug(f"running start version of filters, start filters are {active_node.graph_node.get_graph_start_filters(event_key)}")
            node_filters = active_node.graph_node.get_graph_start_filters(event_key)
        else:
            dev_log.debug(f"running regular event filters: <{active_node.graph_node.get_event_filters(event_key)}>")
            node_filters = active_node.graph_node.get_event_filters(event_key)
            #custom event types designed to have extra addon filters, still being fleshed out as of 3.6.0
            # if hasattr(event, "get_event_filters") and callable(event.get_event_filters):
            #     node_filters = event.get_event_filters()
            #     dialog_logger.debug(f"filters from custom event {node_filters}")
            # else:
            #     node_filters = []

        try:
            return self._filter_list_runner(active_node, event, node_filters, purpose=POSSIBLE_PURPOSES.FILTER)
        except Exception as e:
            exec_log.error(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}>, exception happened when trying to run filters. assuming skip")
            dev_log.error(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}>, exception happened when trying to run filters, details {e}")
            return False
    

    async def _run_actions_on_node(self, active_node:BaseType.BaseNode, event_key:str, event, version:typing.Union[str, None] = None):
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
        control_data = {}
        section_name = "actions"
        if version == "start":
            section_name = "setup"
            callbacks = active_node.graph_node.get_graph_start_setup(event_key)
            exec_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> running start callbacks: <{callbacks}>")
        elif version == "close":
            section_name = "close_actions"
            callbacks = active_node.graph_node.get_node_close_actions()
            exec_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> running closing callbacks: <{callbacks}>")
        else:
            close_flags = active_node.graph_node.get_event_close_flags(event_key)
            control_data = {"close_node": "node" in close_flags, "close_session": "session" in close_flags}
            callbacks = active_node.graph_node.get_event_actions(event_key)
            exec_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> running event callbacks: <{callbacks}>")
        
        old_node_timeout = copy.deepcopy(active_node.timeout) if active_node.timeout is not None else None
        old_session_timeout = copy.deepcopy(active_node.session.timeout) if active_node.session is not None and active_node.session.timeout is not None else None
        before_callbacks_keys = self.active_node_cache.get_all_secondary_keys(id(active_node))
        # this may error, methods that call this one are responsible for error handling
        control_data = await self._action_list_runner(active_node, event, callbacks, POSSIBLE_PURPOSES.ACTION, control_data=control_data, section_name=section_name)

        # in case there were updates that caused changes to keys, shouldn't break anything if no changes made
        if self.get_active_node_key(active_node) in self.active_node_cache:
            self.active_node_cache.set_item(self.get_active_node_key(active_node), active_node, before_callbacks_keys)
        if version is None:
            dev_log.debug(f"action runner is responding to event, could have timeouts being tracked that need updating")
            # only regular event callbacks should check updating timeout trackers
            # start callbacks may change timeout but they haven't been recorded inside tracking yet so that cannot be update call
            self.update_timeout_tracker(active_node, old_node_timeout)
            if active_node.session is not None:
                dev_log.debug(f"action runner is responding to event, updating session timeout waiter <{self.get_session_key(active_node.session)}>")
                self.update_timeout_tracker(active_node.session, old_session_timeout)
            return control_data
        return None
    
    def _run_transition_filters_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''runs filters for transitions for the given node and event. Runs filters for each transition in order and returns the first single transition that passes filters
        
        Return
        ---
        None if no transitions passed, otherwise dictionary that holds settings for the rest of the transition action and running
        - `count` dict of node names to number of copies of graph nodes to create as part of transition
        - `actions` list of actions that handle transition
        - `session_action` what to do with the session when transitioning
        - `session_timeout` if there's an adjustment to session timeout, grabs value from current Active Node
        - `close_flags` if node and/or session should be closed after handling event, value grabbed from yaml'''
        node_transitions = active_node.graph_node.get_transitions(event_key)
        passed_transition = None
        for transition_ind, transition in enumerate(node_transitions):
            dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> starting checking transtion number <{transition_ind}>")
            # first update any counts
            yaml_named_counts = BaseType.BaseGraphNode.parse_node_names(transition["node_names"])
            if "transition_counters" in transition:
                count_results = self._counter_runner(yaml_named_counts, active_node, event, transition["transition_counters"], POSSIBLE_PURPOSES.TRANSITION_COUNTER)
                dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> counters finished executing, counts are {count_results}, node ids <{count_results.keys()}>")
            else:
                count_results = yaml_named_counts
                dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> no counters so counts are {count_results}, node ids <{count_results.keys()}>")
            
            # clean up counts
            for node_name in list(count_results.keys()):
                if node_name not in self.graph_node_indexer:
                    exec_log.warning(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> transition to <{node_name}> transition won't work, goal node doesn't exist.")
                    del count_results[node_name]
            
            # running filters on this transtition
            # if no filters then, auto true result
            # transition filters will receive the full count in goal_name
            filter_res = True
            if "transition_filters" in transition:
                exec_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> has transition filters {transition['transition_filters']}")
                try:
                    filter_res = self._filter_list_runner(active_node, event, transition["transition_filters"], POSSIBLE_PURPOSES.TRANSITION_FILTER, goal_node=count_results)
                    if not isinstance(filter_res, bool):
                        # if any weird resutls, assume false
                        filter_res = False
                except Exception as e:
                    # if any failure, assume false
                    filter_res = False
                    exec_log.error(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> exception happened when trying to filter transitions. assuming skip")
                    dev_log.error(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition <{transition_ind}> exception happened when trying to filter transitions, details {e}")
            
            if filter_res:
                transition_close_flag = []
                if "schedule_close" in transition:
                    transition_close_flag = transition["schedule_close"]
                passed_transition = {
                    "count": count_results,
                    "actions": transition["transition_actions"],
                    "session_action": (transition["session_chaining"] if isinstance(transition["session_chaining"], str) else list(transition["session_chaining"].keys())[0])
                                    if "session_chaining" in transition else "end",
                    "session_timeout": None if "session_chaining" not in transition or isinstance(transition["session_chaining"], str) else list(transition["session_chaining"].values())[0],
                    "close_flags": transition_close_flag
                }
                return passed_transition
        return None
        
    async def _run_transitions_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''handles transitions for a node (not including closing current one if needed) for the given active node and event.
        Calls to running transition filters to find transition that passes then sets up next nodes and runs actions on all next nodes'''
        dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> starting handling transitions")
        passed_transition = self._run_transition_filters_on_node(active_node, event_key, event)
        if passed_transition is None:
            return {"close_node": False, "close_session": False}
        dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> transition that passed filters are for nodes <{passed_transition['count']}>, now starting transitions")
        
        session_action = passed_transition["session_action"]
        session_timeout = passed_transition["session_timeout"]

        section_exceptions = []
        callbacks_list:list[typing.Tuple[BaseType.BaseNode, list, int]] = []
        # first pass is setting up active nodes and sessions for callbacks to work on
        for next_node_name, count in passed_transition["count"].items():
            for i in range(count):
                dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> setting up node <{next_node_name}> number <{i}>")
                session = None
                if session_action == "start" or (session_action == "chain" and active_node.session is None):
                    # start or chaining when no current session
                    dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> starting session for transition to goal <{next_node_name}>")
                    if session_timeout is not None:
                        session = SessionData.SessionData(timeout_duration=timedelta(seconds=session_timeout))
                    else:
                        session = SessionData.SessionData()
                    dev_log.debug(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> session debugging, started new session, id is <{self.get_session_key(session)}>, timeout is {session.time_left()}")
                elif session_action in ["chain", "section"] and active_node.session is not None:
                    # regular behavior for chain, select session if it exists
                    # only chain and section need to care about session already existing and changing timeout
                    if session_timeout is not None:
                        old_session_timeout = copy.deepcopy(active_node.session.timeout) if active_node.session.timeout is not None else None
                        active_node.session.set_TTL(timeout_duration=timedelta(seconds=session_timeout))
                        self.update_timeout_tracker(active_node.session, old_session_timeout)
                    session = active_node.session
                    dev_log.debug(f"next node starting with current active session. <{self.get_session_key(session)}>")
                elif session_action != "end":
                    dev_log.debug(f"next node starting with current active session. <{self.get_session_key(session)}>")
                    # end means next node doesn't get current session, all other cases can take current session, though if it was session object it most likely was handled already
                    session = active_node.session

                next_node = self.graph_node_indexer.get_ref(next_node_name).activate_node(session)
                if session_action == "section" and session is not None:
                    # not the complete list of all nodes created. might miss sone when ending session, might have extra when starting session but at least covers all that would be in the session about to be sectioned
                    section_exceptions.append(next_node)
                exec_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> activated next node, <{id(next_node)}><{next_node_name}>, copy <{i}>")
                if session_action != "end" and session is not None:
                    # only end doesn't want node added to session
                    dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> adding next node <{id(next_node)}><{next_node.graph_node.id}> to session <{self.get_session_key(session)}>")
                    session.add_node(next_node)
                    dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> session debugging, session <{self.get_session_key(session)}>, now has node list is <{[str(self.get_active_node_key(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
                callbacks_list.append((next_node, passed_transition["actions"], i))

        # all setup, do all changes
        for callback_settings in callbacks_list:
            next_node = callback_settings[0]
            action_list = callback_settings[1]
            copy_num = callback_settings[2]
            dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> executing transition actions for next node <{self.get_active_node_key(next_node)}><{next_node.graph_node.id}> copy <{copy_num}> list: <{action_list}>")
            control_data = self.generate_action_control_data({"copy":copy_num})
            # session could be chained and thus something that is already registered and timeout could be changed during actions
            # node is always new so no need to grab old timeout
            old_session_timeout = copy.deepcopy(next_node.session.timeout) if next_node.session is not None and next_node.session.timeout is not None else None
            before_callbacks_keys = self.active_node_cache.get_all_secondary_keys(self.get_active_node_key(active_node))
            await self._action_list_runner(active_node, event, action_list, POSSIBLE_PURPOSES.TRANSITION_ACTION, goal_node=next_node, control_data=control_data, section_name="transition_actions")
            dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> finished transition actions for next node <{self.get_active_node_key(next_node)}><{next_node.graph_node.id}> copy <{copy_num}>")
            self.active_node_cache.set_item(self.get_active_node_key(active_node), active_node, before_callbacks_keys)
            if next_node.session is not None and len(self.get_active_timeout_tracker(next_node.session)) > 0:
                self.update_timeout_tracker(next_node.session, old_session_timeout)
            await self._track_new_active_node(next_node, event)
        
        if session_action == "section" and active_node.session is not None:
            dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_key}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> sectioning, closing nodes from before transition")
            await self.clear_session_history(active_node.session, exceptions=section_exceptions)
        
        return {"close_node": "node" in  passed_transition["close_flags"], "close_session": "session" in  passed_transition["close_flags"]}


    '''#############################################################################################
    ################################################################################################
    ####                   I-DONT-REALLY-HAVE-A-NAME-BUT-IT-DOESNT-FIT-ELSEWHERE SECTION
    ################################################################################################
    ################################################################################################'''

    async def _track_new_active_node(self, active_node:BaseType.BaseNode, event):
        '''adds the given active node to handler's internal tracking. after this, node is fully considered being managed by this handler.
        adds node to handler's list of active nodes its currently is waiting on, does node actions for entering node, adds info about what events node
        is waiting for, and adds trackers for timeouts'''
        dev_log.info(f"handler id'd <{id(self)}> adding node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> to internal tracking and running node callbacks")
        active_node.activate()

        await self._action_list_runner(active_node, event, active_node.graph_node.get_node_actions(), POSSIBLE_PURPOSES.ACTION, control_data={})
        
        self.create_timeout_tracker(active_node)
        if active_node.session is not None:
            if len(self.get_active_timeout_tracker(active_node.session)) == 0:
                # only tracks session timeout if it is new thing to track, assume outside needs to update if it is already tracked
                self.create_timeout_tracker(active_node.session)
        self.active_node_cache.add_item(self.get_active_node_key(active_node), active_node)
        dev_log.info(f"handler id'd <{id(self)}> finished adding tracking for node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}>")
        
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
        dev_log.info(f"handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> starting closing")
        if not active_node.is_active():
            return
        active_node.notify_closing()
        exec_log.info(f"handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> losing. timed out? <{timed_out}>, emergency? <{emergency_remove}>")
        if not emergency_remove:
            try:
                await self._run_actions_on_node(active_node, "close", {"timed_out":timed_out}, version="close")
            except Exception as e:
                pass
            dev_log.info(f"handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> finished custom callbacks closing node, now clearing node from internal trackers")

        active_node.close()

        # this section closes the session if no other nodes in it are active. make sure sectioning session doesn't clear out all nodes
        if active_node.session and active_node.session is not None:
            exec_log.debug(f"handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> close_node checking linked session is dead <{self.get_session_key(active_node.session)}>")
            printing_active = [node.graph_node.id for node in active_node.session.get_linked_nodes()]
            dev_log.debug(f"linked nodes to check are <{[f'<{str(self.get_active_node_key(node))}><{node.graph_node.id}> <{node.is_active()}>' for node in active_node.session.get_linked_nodes()]}>")
            session_void = True
            for node in active_node.session.get_linked_nodes():
                if node.is_active():
                    session_void = False
                    break
            
            if session_void:
                exec_log.debug(f"handler id'd <{id(self)}> node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> close_node found linked session is dead <{self.get_session_key(active_node.session)}>")
                await self.close_session(active_node.session, timed_out=timed_out)

        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.cache.items()}
        dev_log.debug(f"before remove, state is active nodes are <{printing_active}>")
        # printing_forwarding = {event:[str(x)+' '+self.active_node_cache.get(x)[0].graph_node.id for x in nodes] for event, nodes in self.active_node_cache.items(index_name="event_forwarding")}
        # dialog_logger.debug(f"current state is event forwarding <{printing_forwarding}>")

        self.active_node_cache.remove_item(self.get_active_node_key(active_node))
        # don't need to worry about timeout. it will find that node is closed and stop
        printing_active = {x: node.graph_node.id for x, node in self.active_node_cache.cache.items()}
        dev_log.debug(f"after remove, state is active nodes are <{printing_active}>")
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
        exec_log.debug(f"handler id'd <{id(self)}> closing session <{self.get_session_key(session)}>, current nodes <{[str(self.get_active_node_key(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
        session.notify_closing()
        await self.clear_session_history(session, timed_out=timed_out)
        session.close()
        # don't need to worry about timeout, it will find that session is closed and stop


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
        `dict` the control data changed by callbacks. currently holds `close_node` and `close_session`, both default to False. cleans up changes due to callbacks'''
        final_control_data = control_data
        control_keys = final_control_data.keys()
        if control_data is None:
            # object meant for temp just passing data to rest of functions in this section.
            control_data = self.generate_action_control_data()
        else:
            control_data = copy.deepcopy(control_data)
        section_data = {}
        async def recur_list_helper(func_sub_list):
            nonlocal control_data
            nonlocal section_data
            nonlocal final_control_data
            for callback in func_sub_list:
                dev_log.debug(f"callback is {callback}, data {section_data}")
                if isinstance(callback, str):
                    # is just function name, no parameters
                    await self._run_func_async(callback, purpose, active_node, event, goal_node=goal_node, callb_section_data=section_data, control_data=control_data, section_name=section_name)
                elif isinstance(callback, SectionUtils.IfSubSection):
                    filter_res = self._filter_list_runner(active_node=active_node, event=event, filter_list=callback.filters, purpose=POSSIBLE_PURPOSES.FILTER, section_data=section_data)
                    if filter_res:
                        await recur_list_helper(callback.actions)
                else:
                    key = list(callback.keys())[0]
                    value = callback[key]
                    await self._run_func_async(key, purpose, active_node, event, goal_node=goal_node, base_parameter=value, callb_section_data=section_data, control_data=control_data, section_name=section_name)
                cleaned_control_data = {}
                for key in control_keys:
                    if key in control_data:
                        cleaned_control_data[key] = control_data[key]
                        final_control_data[key] = control_data[key]
                control_data = cleaned_control_data
        await recur_list_helper(action_list)
        return final_control_data
    
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
                elif isinstance(filter, SectionUtils.LogicOpSubSection):
                    if filter.name == "not":
                        filter_run_result = not recur_list_helper(filter.callbacks, operator="and")
                    else:
                        filter_run_result = recur_list_helper(filter.callbacks, operator=filter.name)
                else:
                    # is a dict representing function call with arguments or nested operator, should only have one key:value pair
                    key = list(filter.keys())[0]
                    value = filter[key]

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
            dev_log.debug(f"Dialog handler id'd <{id(self)}> tried running function named <{func_name}> for node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>, not allowed")
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                # filter functions, whether transtion or not, expect bool returns. must return some bool and assume not allowed
                # (function not listed in handler, or running for wrong purpose) means failed filter
                return False
            else:
                return None
        dev_log.debug(f"Dialog handler id'd <{id(self)}> starting running function named <{func_name}> for node <{self.get_active_node_key(active_node)}><{active_node.graph_node.id}> section <{purpose}> event id'd <{id(event)}> type <{type(event)}>")
        func_ref = self.functions_cache.get(func_name)[0]["ref"]
        datapack = CbUtils.CallbackDatapack(
                                            active_node=active_node,
                                            event=event,
                                            base_parameter=copy.deepcopy(base_parameter) if base_parameter is not None else None,
                                            goal_node_name=goal_node if isinstance(goal_node, str) else None,
                                            goal_node=goal_node if not isinstance(goal_node, str) else None,
                                            section_name=section_name,
                                            section_data=callb_section_data if callb_section_data is not None else {},
                                            control_data=control_data if control_data is not None else {},
                                            section_progress=section_progress if section_progress is not None else {},
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
    
    def get_active_node_key(self, active_node): #TODO: double check all accessors have been converted to this function
        '''wrapper for how the system determines for ids of active nodes. Just to make sure it is consistent across the handler'''
        return id(active_node)
    
    def get_session_key(self, session):
        '''wrapper for how the system determines for ids of sessions. Just to make sure it is consistent across the handler'''
        return id(session)

    '''#############################################################################################
    ################################################################################################
    ####                                       TASK MANGEMENT SECTION
    ################################################################################################
    ################################################################################################'''
    def _filter_active_tasks(self, task_list:'list[HandlerTasks.HandlerTask]'):
        '''extra cleaning of old tasks that should be removed. main benefit is just makes lists shorter'''
        filtered_list = []
        for task in task_list:
            dev_log.debug(f"checking up on task <{id(task)}>, done? <{task.done()}> exception <{task.exception() if task.done() else 'not done'}>")
            if task.stop_time is not None and task.stop_time + self.settings.task_age < datetime.utcnow():
                self.advanced_event_queue.remove_item(id(task))
                # break any potential circular references. should not happen when using pattern of events in tracking is only previous scheduled tasks
                task.locking_tasks.clear()
                continue
            filtered_list.append(task)
        return filtered_list

    def _create_handle_event_task(self, event_type, event):
        dev_log.info(f"handler id'd <{id(self)}> has been notified of event happening. event <{id(event)}><{event_type}> oject type <{type(event)}>, creating task for handling")
        to_await_event_tasks = []
        existing_event_tasks:list[HandlerTasks.HandlerTask] = self.advanced_event_queue.get("EventTask", index_name="task_type", default=[])
        existing_event_tasks = self._filter_active_tasks(existing_event_tasks)
        if self.settings.strict_event_order:
            to_await_event_tasks.extend(existing_event_tasks)
        task = HandlerTasks.HandleEventTask(handler_func=self._handle_event_task, event_type=event_type, event=event, locking_tasks=to_await_event_tasks)
        dev_log.debug(f"task for <{id(event)}><{event_type}> task is <{id(task)}> waiting on other tasks. locking tasks are <{[id(item) for item in to_await_event_tasks]}>")
        self.advanced_event_queue.add_item(id(task), task)
        return task
    
    async def _handle_event_task(self, event_type, event, waiting_period_sec):
        dev_log.info(f"handler id'd <{id(self)}> event <{id(event)}><{event_type}> starting handling")
        waiting_node_keys = self.active_node_cache.get_keys(event_type, index_name="event_forwarding", default=[])
        dev_log.debug(f"handler id'd <{id(self)}>, event <{id(event)}><{event_type}> nodes waiting for event are <{[f'<{str(self.get_active_node_key(self.active_node_cache.get_ref(x)))}><{self.active_node_cache.get_ref(x).graph_node.id}>' for x in waiting_node_keys]}>")
        # don't use gather here, think it batches it so all nodes responding to event have to pass callbacks before any one of them go on to transitions
        # each node is mostly independent of others for each event and don't want them to wait for another node to finish
        
        session_tasks = {}
        '''track sessions that are involved for the nodes we are trying to run on'''
        node_tasks = []
        '''tasks for all nodes to run on'''

        # new event needs to be scheduled for all nodes that are waiting for it
        # either at same time as previous events or after, is a setting
        # for a event running on node, needs to wait until previous events on session and node are done
        for node_key in waiting_node_keys:
            node_locking_tasks = []
            session_locking_tasks = []
            node = self.active_node_cache.get_ref(node_key)
            if node.session is not None:
                # find if there's any previous events still being processed for the session
                found_session_tasks = self.advanced_event_queue.get(self.get_session_key(node.session), index_name="session_id", default=[])
                found_session_tasks = self._filter_active_tasks(found_session_tasks)
                node_locking_tasks.extend(found_session_tasks)
                session_locking_tasks.extend(found_session_tasks)
                found_session_timeouts = self.advanced_event_queue.get(self.get_session_key(node.session), index_name="session_timeouts",default=[])
                found_session_timeouts = self._filter_active_tasks(found_session_timeouts)
                node_locking_tasks.extend(found_session_timeouts)
                session_locking_tasks.extend(found_session_timeouts)
            # find if any previous events still being processed for the node
            found_node_tasks = self.advanced_event_queue.get(self.get_active_node_key(node), index_name="node_id", default=[])
            found_node_tasks = self._filter_active_tasks(found_node_tasks)
            node_locking_tasks.extend(found_node_tasks)
            # also wait for timeout events
            timeout_tasks = self.advanced_event_queue.get(self.get_active_node_key(node), index_name="node_timeouts", default=[])
            timeout_tasks = self._filter_active_tasks(timeout_tasks)
            node_locking_tasks.extend(timeout_tasks)
            node_task = HandlerTasks.HandleNodeEventTask(self._run_event_on_node, active_node=node, event=event, event_type=event_type, locking_tasks=node_locking_tasks, waiting_period_sec=waiting_period_sec)
            dev_log.debug(f"task created for running event <{id(event)}><{event_type}> on <{self.get_active_node_key(node)}><{node.graph_node.id}>, id <{id(node_task)}> locking are: {[id(task) for task in node_locking_tasks]}")
            if node.session is not None and self.get_session_key(node.session) not in session_tasks:
                # there won't be a session for this event yet since still processing and adding to trackers is last step
                # for list of nodes that are responding to this event, session can repeat. so have a separate list tracking
                #   unique sessions to create and add for this event
                session_task = HandlerTasks.HandleSessionEventTask(self.session_event_task, session=node.session, event=event, event_type=event_type, locking_tasks=session_locking_tasks, waiting_period_sec=waiting_period_sec)
                dev_log.debug(f"task created for running event <{id(event)}><{event_type}> on session <{self.get_session_key(node.session)}>, id <{id(session_task)}> locking are: {[id(task) for task in session_locking_tasks]}")
                session_tasks[self.get_session_key(node.session)] = session_task
            node_tasks.append(node_task)
        # only add the current event tasks to tracking after processing so can't accidentally wait on task from this round
        for task in node_tasks:
            self.advanced_event_queue.add_item(id(task), task)
        for task in session_tasks.values():
            task.set_node_tasks(node_tasks)
            self.advanced_event_queue.add_item(id(task), task)

        notify_results = await asyncio.gather(*[*node_tasks, *session_tasks.values()])
        dev_log.debug(f"handler id'd <{id(self)}>, event <{id(event)}> end of handle_event results are <{notify_results}>")

    async def session_event_task(self, session, event_type, event, node_tasks):
        dev_log.debug(f"handler id'd <{id(self)}>, handling event <{id(event)}><{event_type}> for session <{self.get_active_node_key(session)}> starting session task, waiting on <{[id(task) for task in node_tasks]}>")
        await asyncio.gather(*node_tasks)
        dev_log.debug(f"handler id'd <{id(self)}>, handling event <{id(event)}><{event_type}> for session <{self.get_active_node_key(session)}> finished waiting for node events")
        close_session = False
        for node_task in node_tasks:
            if node_task.done() and node_task.exception() is None:
                result:RunNodeEventOutput = node_task.result()
                if result is not None and result.close_session is not None:
                    close_session = close_session or result.close_session
        if close_session:
            dev_log.debug(f"handler id'd <{id(self)}>, handling event <{id(event)}><{event_type}> for session <{self.get_active_node_key(session)}> found needs to close session")
            await self.close_session(session)

    async def wait_timeout(self, timeoutable, waiting_seconds):
        task = asyncio.current_task()
        if issubclass(timeoutable.__class__, BaseType.BaseNode):
            type = "Node"
        elif isinstance(timeoutable, SessionData.SessionData):
            type = "Session"
        else:
            return
        
        # big outer loop for repeating waiting for timeout, then when it hits run timeout callbacks. just has the regular conditions
        #   for not needing to check timeouts anymore: doesn't timeout or timeout has passed
        while timeoutable.timeout is not None and datetime.utcnow() <= timeoutable.timeout:
            # the keep checking loop
            while datetime.utcnow() < timeoutable.timeout:
                task.status = TASK_STATE.WAITING
                # try to sleep at most the given waiting_seconds just so is somewhat active and can respond to cancels or changes
                delay = min(max(0, (timeoutable.timeout - datetime.utcnow()).total_seconds()), waiting_seconds)
                dev_log.debug(f"handler id'd <{id(self)}> waiting for a timeout for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. sleeping for <{delay}>")
                await asyncio.sleep(delay)
                if timeoutable.status == ITEM_STATUS.CLOSED or timeoutable.timeout is None:
                    dev_log.debug(f"handler id'd <{id(self)}> after waiting for a timeout for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. found it is closed or timeout disabled")
                    # if timeout was stopped or node already closed, don't need to continue checking and running
                    return
            task.status = TASK_STATE.EVENT
            existing_event_tasks = []
            if not self.settings.timeout_cut and self.settings.strict_event_order:
                existing_event_tasks:list[HandlerTasks.HandlerTask] = self.advanced_event_queue.get("EventTask", index_name="task_type", default=[])
                existing_event_tasks = self._filter_active_tasks(existing_event_tasks)
            timeout_handler_task = HandlerTasks.HandleTimeoutTask(self.handle_timeout, timeoutable=timeoutable, type=type, locking_tasks=existing_event_tasks, waiting_period_sec=waiting_seconds)
            dev_log.debug(f"handler id'd <{id(self)}> timeout waiter for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. timeout handler task <{id(timeout_handler_task)}> locking tasks found to be <{[id(task) for task in existing_event_tasks]}>")
            self.advanced_event_queue.add_item(id(timeout_handler_task), timeout_handler_task)
            dev_log.debug(f"task queue size <{len(self.advanced_event_queue)}>")
            await timeout_handler_task
            if timeoutable.status == ITEM_STATUS.CLOSED:
                return

    async def handle_timeout(self, timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData], waiting_seconds):
        event = {}
        if issubclass(timeoutable.__class__, BaseType.BaseNode):
            type = "Node"
            session = timeoutable.session
            nodes = [timeoutable]
        elif isinstance(timeoutable, SessionData.SessionData):
            type = "Session"
            session = timeoutable
            nodes = [*timeoutable.linked_nodes]
        dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. started")

        # session may be none because node doesn't have a session.
        # there is at max one session
        # nodes are either one or all of the same session

        session_task = None
        node_tasks = []
        '''tasks for all nodes to run on'''

        session_locking_tasks = []
        if session is not None:
            found_session_tasks = self.advanced_event_queue.get(self.get_session_key(session), index_name="session_id", default=[])
            found_session_tasks = self._filter_active_tasks(found_session_tasks)
            session_locking_tasks.extend(found_session_tasks)
            session_task = HandlerTasks.HandleSessionEventTask(self.session_event_task, session=session, event=event, event_type="timeout", locking_tasks=session_locking_tasks, waiting_period_sec=waiting_seconds)
            dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. created session task <{id(session_task)}> for session <{self.get_session_key(session)}>, locking tasks are <{[id(task) for task in session_locking_tasks]}>")

        # new event needs to be scheduled for all nodes that are waiting for it
        # either at same time as previous events or after, is a setting
        # for a event running on node, needs to wait until previous events on session and node are done
        for node in nodes:
            node_locking_tasks = []
            if session is not None:
                # find if there's any previous events still being processed for the session
                node_locking_tasks.extend(found_session_tasks)
            # find if any previous events still being processed for the node
            found_node_tasks = self.advanced_event_queue.get(self.get_active_node_key(node), index_name="node_id", default=[])
            found_node_tasks = self._filter_active_tasks(found_node_tasks)
            node_locking_tasks.extend(found_node_tasks)

            node_task = HandlerTasks.HandleNodeEventTask(self._run_event_on_node, active_node=node, event=event, event_type="timeout", locking_tasks=node_locking_tasks, waiting_period_sec=waiting_seconds)
            dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. created node task <{id(node_task)}> for node <{self.get_active_node_key(node)}>, locking tasks are <{[id(task) for task in node_locking_tasks]}>")
            node_tasks.append(node_task)
        dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. adding tasks to tracking")
        # only add the current event tasks to tracking after processing so can't accidentally wait on task from this round
        final_await_list = []
        for task in node_tasks:
            final_await_list.append(task)
            self.advanced_event_queue.add_item(id(task), task)
        if session_task:
            session_task.set_node_tasks(node_tasks)
            self.advanced_event_queue.add_item(id(session_task), session_task)
            final_await_list.append(session_task)
        dev_log.debug(f"task queue size <{len(self.advanced_event_queue)}>")
        dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. tasks for timeout are <{[id(task) for task in node_tasks]}>")
        await asyncio.gather(*final_await_list)
        if timeoutable.timeout is not None and timeoutable.timeout <= datetime.utcnow():
            dev_log.debug(f"handler id'd <{id(self)}> timeout handler for <{type}><{self.get_active_node_key(timeoutable) if type == 'Node' else self.get_session_key(timeoutable)}>. found timeout gone, need to close")
            if type == "Node":
                await self.close_node(timeoutable)
            else:
                await self.close_session(timeoutable)

    '''#############################################################################################
    ################################################################################################
    ####                                       CLEANING OUT NODES SECTION
    ################################################################################################
    ################################################################################################'''

    # there's only one task that handles organizing how to respond to timeout events

    def get_active_timeout_tracker(self,
                               timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData]):
        '''task queue may have finished events hanging around, filter for active timeout trackers'''
        if timeoutable.timeout is None:
            # none means no timeout at all. don't need a task.
            return []
        fetched_list = []
        if issubclass(timeoutable.__class__, BaseType.BaseNode):
            fetched_list = self.advanced_event_queue.get_keys(self.get_active_node_key(timeoutable), index_name="node_waiters", default=[])
        elif isinstance(timeoutable, SessionData.SessionData):
            fetched_list = self.advanced_event_queue.get_keys(self.get_session_key(timeoutable), index_name="session_waiters", default=[])
        filtered_list = []
        for timeout_waiter_key in fetched_list:
            timeout_waiter = self.advanced_event_queue.get_ref(timeout_waiter_key)
            if not timeout_waiter.done():
                filtered_list.append(timeout_waiter)
        return filtered_list

    def create_timeout_tracker(self,
                               timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData]):
        '''create task object that is responsible for firing tieout event on given node or session.
        Handler will keep track of the task'''
        if timeoutable.timeout is None:
            # none means no timeout at all. don't need a task.
            return
        if len(self.get_active_timeout_tracker(timeoutable)) > 0:
            # there's already a tracker recorded
            return
        if issubclass(timeoutable.__class__, BaseType.BaseNode):
            task = HandlerTasks.HandleTimeoutWaiter(self.wait_timeout, timeoutable, waiting_period_sec=4)
            dev_log.debug(f"handler id'd <{id(self)}> creating timeout task <{id(task)}> for node <{self.get_active_node_key(timeoutable)}><{timeoutable.graph_node.id}>, handling happens in <{timeoutable.time_left()}>")
            self.advanced_event_queue.add_item(id(task), task)
        elif isinstance(timeoutable, SessionData.SessionData):
            task = HandlerTasks.HandleTimeoutWaiter(self.wait_timeout, timeoutable, waiting_period_sec=4)
            dev_log.debug(f"handler id'd <{id(self)}> creating timeout task <{id(task)}> for session <{self.get_session_key(timeoutable)}>, handling happens in <{timeoutable.time_left()}>")
            self.advanced_event_queue.add_item(id(task), task)

    def update_timeout_tracker(self,
                               timeoutable:typing.Union[BaseType.BaseNode, SessionData.SessionData],
                               old_timeout):
        '''updates internal tracking if there are changes to timeout that would cause significant difference.
        timeout shortened, creates new task if existing was sleeping. timeout removed, removes tracking'''
        if issubclass(timeoutable.__class__, BaseType.BaseNode):
            timeoutable_id = self.get_active_node_key(timeoutable)
            type = "Node"
        else:
            timeoutable_id = self.get_session_key(timeoutable)
            type = "Session"
            dev_log.debug(f"updating timeout tracker for a session. think id is <{timeoutable_id}>, new timeout {timeoutable.timeout} odl timeout is {old_timeout}")
            dev_log.debug(f"current status is <{[id(self.advanced_event_queue.get_ref(task_key).timeoutable) for task_key in self.advanced_event_queue.get_keys('TimeoutWaiter', index_name='task_type')]}>")
        if timeoutable.timeout is not None:
            # there is a timeout on item
            if old_timeout is None:
                # newly created timeout, so need to add tracker
                self.create_timeout_tracker(timeoutable)
            elif len(self.get_active_timeout_tracker(timeoutable)) == 0:
                # error case, if there's an old timeout there should be something in trackers.
                #  but not terrible if it isn't there
                self.create_timeout_tracker(timeoutable)
                #v3.8 transitioned to tasks. removing the part about checking if changed to shorter timeout and recreating task
                # since it's a little bit much to juggle the timeout task checking if it is the "main" task allowed to run the
                # timeout event stuff. This means the timeout tasks will have to wake up by itself to check if things changed and
                # timeout handling is limited to that speed. might be some slowness when updating to shorter timeout
        
    async def clean_task(self, task_period:float):
        this_cleaning = asyncio.current_task()
        cleaning_logger.info(f"clean task id <{id(this_cleaning)}><{this_cleaning}> starting, period is <{task_period}>")
        # want forever running task while handler is alive
        while True:
            tasks_list = list(self.advanced_event_queue.cache.values())
            self._filter_active_tasks(tasks_list)
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
            dev_log.warning(f"destrucor for handler. id'd <{id(self)}> sanity checking any memory leaks, may not be major thing" +\
                                  f"nodes left: <{printing_active}>")
