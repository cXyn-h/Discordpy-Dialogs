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
from src.utils.Enums import POSSIBLE_PURPOSES

import src.utils.SessionData as SessionData
# validating function data
from jsonschema import validate, ValidationError
# type annotations
import src.DialogNodes.BaseType as BaseType

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

#NOTE: each active node will get a reference to handler. Be careful what callbacks are added as they can mess around with handler itself

class DialogHandler():
    def __init__(self, nodes:"dict[str, BaseType.BaseGraphNode]"=None, functions=None, settings = None, clean_freq_secs = 3, **kwargs) -> None:
        self.graph_nodes:dict[str, BaseType.BaseGraphNode] = nodes if nodes is not None else {}
        '''dict of nodes that represent graph this handler controls. other handlers linking to same list is ok and on dev to handle.'''
        self.functions = functions if functions is not None else {}
        '''dict of functions this handler is allowed to call. other handlers linking to same list is ok and on dev to handle.'''

        self.active_nodes:dict[int,BaseType.BaseNode]={}
        '''dictionary of active nodes that this handler is in charge of events and advancing. is mapping of unique id to node object'''
        self.event_forwarding={}

        self.sessions:dict[int,SessionData.SessionData] = {}
        #TODO: not relly using the session finding dict
        self.session_finding = {}

        #TODO: still need to integrate and use these settings everywhere, especially the reading sections
        #       but before doing that probably want to think through what reporting will look like, where should reports go: dev, operator, server logs, bot logs?
        self.settings = copy.deepcopy(settings) if settings is not None else {}
        if "exception_level" not in self.settings:
            self.settings["exception_level"] = "ignore"

        self.cleaning_task = None
        self.clean_freq_secs = clean_freq_secs

        self.register_module(BaseFuncs)

        for key, option in kwargs.items():
            setattr(self, key, option)
    
    '''################################################################################################
    #
    #                                   SETUP FUNCTIONS SECTION
    #
    ################################################################################################'''

    def setup_from_files(self, file_names:"list[str]" = []):
        '''override current graph with nodes in the passed in files. if you already read nodes from these files outside this class,
        consider passing the list of nodes into the constructor.'''
        #TODO: second pass ok and debug running
        self.graph_nodes=nodeParser.parse_files(*file_names, existing_nodes={})

    def add_nodes(self, node_list:"dict[int, BaseType.BaseGraphNode]" = {}):
        '''add all nodes in list into handler. gives a warning on duplicates
         dev note: assumed handler is now responsible for the objects passed in'''
        #TODO: second pass ok and debug running
        for node in node_list.values():
            if node.id in self.graph_nodes:
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
        permitted_purposes = func.allowed
        if "allowed" in override_settings:
            permitted_purposes = override_settings["allowed"]
        
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
        
        dialog_logger.debug(f"registered callback <{func}> with key <{cb_key}> for purposes: <{permitted_purposes}>")
        #TODO: this needs upgrading if doing qualified names
        self.functions[cb_key]= {"ref":func, "permitted_purposes":permitted_purposes}
        return True
    
    def register_module(self, module):
        for func, overrides in module.dialog_func_info.items():
            self.register_function(func, overrides)

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
        if section not in self.functions[func_name]["ref"].allowed:
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
        execution_reporting.info(f"starting process to start at node <{node_id}> with event <{event_key}> event deets: id <{id(event)}> type <{type(event)}>")
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
            dialog_logger.info(f"start at found node starts with a session")
            session = SessionData.SessionData()
        
        # get active node, design is callbacks assume have an active node to act on, allowing reusing those for start section (and reducing functions
        #   to maintain/store) means want an active node before processing callbacks
        active_node:BaseType.BaseNode = graph_node.activate_node(session)
        # some callbacks may depend on this assignment
        active_node.assign_to_handler(self)
        dialog_logger.debug(f"starting session setup process to start <{node_id}> with event key <{event_key}> id'd <{id(event)}> oject type <{type(event)}>")
        # some filters may want to depend on session data, which usually gets chance to setup on transition. Startup doesn't get any other chance
        #   than running some callbacks before filters
        await self.run_event_callbacks_on_node(active_node, event_key, event, version="start")
        dialog_logger.debug(f"starting custom filter process to start <{node_id}> with event key <{event_key}> id'd <{id(event)}> oject type <{type(event)}>")
        start_filters_result = self.run_event_filters_on_node(active_node, event_key, event, start_version=True)
        if start_filters_result:
            dialog_logger.info(f"starting node <{node_id}> with event key <{event_key}> id'd <{id(event)}>")
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
        dialog_logger.debug(f"results returned to notify method are <{notify_results}>")

    '''################################################################################################
    #
    #                                       RUNNING EVENTS SECTION
    #
    ################################################################################################'''

    async def run_event_on_node(self, active_node:BaseType.BaseNode, event_key:str, event):
        '''processes event happening on the given node'''
        execution_reporting.debug(f"running event type <{event_key}> on node <{id(active_node)}><{active_node.graph_node.id}>")
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
        if should_close_node and active_node.is_active:
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
        dialog_logger.debug(f"run event filters. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, type of event <{type(event)}> filters: <{active_node.graph_node.get_event_filters(event_key)}>")
        
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
        dialog_logger.info(f"adding node <{id(active_node)}><{active_node.graph_node.id}> to internal tracking")
        active_node.assign_to_handler(self)

        await self.action_list_runner(active_node,event, active_node.graph_node.get_callbacks(), POSSIBLE_PURPOSES.ACTION)

        self.active_nodes[id(active_node)] = active_node
        for listed_event in active_node.graph_node.get_events().keys():
            if listed_event not in self.event_forwarding:
                self.event_forwarding[listed_event] = set()
            self.event_forwarding[listed_event].add(active_node)

        #not adding register session cause most likely passing in new node every time, but not gauranteed unique session every new node. (even though currently that's technically not an issue)
        
        # used to have autoremoval for nodes that aren't waiting for anything, but found there might be cases where want to keep node around
        # if len(active_node.graph_node.get_events()) < 1:
        #     await self.close_node(active_node, timed_out=False)


    async def close_node(self, active_node:BaseType.BaseNode, timed_out=False, emergency_remove = False):
        execution_reporting.info(f"closing node <{id(active_node)}><{active_node.graph_node.id}> timed out? <{timed_out}>")
        if not emergency_remove:
            await self.run_event_callbacks_on_node(active_node, "close", {"timed_out":timed_out}, version="close")

        active_node.close_node()
        # this section closes the session if no other nodes in it are active. causing issues with sectioning session into steps (which clears recorded nodes when going to next step)
        # if active_node.session and active_node.session is not None:
        #     session_void = True
        #     for node in active_node.session.get_linked_nodes():
        #         if node.is_active:
        #             session_void = False
        #             break
            
        #     if session_void:
        #         await self.close_session(active_node.session)
        dialog_logger.info(f"finished custom callbacks closing <{id(active_node)}><{active_node.graph_node.id}>, clearing node from internal trackers")
        printing_active = {x: node.graph_node.id for x, node in self.active_nodes.items()}
        dialog_logger.debug(f"current state is active nodes are <{printing_active}>")
        printing_forwarding = {event:[str(id(x))+' '+x.graph_node.id for x in nodes] for event,nodes in self.event_forwarding.items()}
        dialog_logger.debug(f"current state is event forwarding <{printing_forwarding}>")
        if id(active_node) in self.active_nodes:
            del self.active_nodes[id(active_node)]
        for event in active_node.graph_node.get_events().keys():
            if event is not None and event in self.event_forwarding:
                self.event_forwarding[event].remove(active_node)

    def register_session(self, session:SessionData.SessionData):
        '''adds the given session info to handler's internal tracking for sessions'''
        if session is None:
            dialog_logger.warning(f"somehow wanting to add none session, should not happen")
            return
        self.sessions[id(session)] = session
    
    async def clear_session_history(self, session:SessionData.SessionData, timed_out=False):
        for node in session.get_linked_nodes():
            if node.is_active:
                await self.close_node(node, timed_out=timed_out)
        session.clear_session_history()
    
    async def close_session(self, session:SessionData.SessionData, timed_out=False):
        execution_reporting.debug(f"closing session <{id(session)}>, current nodes <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
        await self.clear_session_history(session, timed_out=timed_out)
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
            for filter in filter_list:
                # dialog_logger.debug(f"testing recursive helper, at filter {filter} in list for node <{id(active_node)}><{active_node.graph_node.id}>")
                if isinstance(filter, str):
                    # filter_run_result = run_filter(handler, filter, active_node, event, None)
                    filter_run_result = self.run_func(filter, purpose, active_node, event, goal_node=goal_node)
                else:
                    # is a dict representing function call with arguments or nested operator, should only have one key
                    key = list(filter.keys())[0]
                    value = filter[key]
                    if key in ["and", "or"]:
                        filter_run_result = self.filter_list_runner(active_node, event, value, purpose, goal_node, operator=key)
                    else:
                        # argument in vlaue is expected to be one object. a list, a dict, a string etc
                        # filter_run_result = run_filter(handler, key, active_node, event, value)
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
        parameters will be passed in this order: the active node instance, the event that happened to node, the next node name if transition filter or active
        next node if transition callback otherwise nothing here, and then if it exists any extra arguments to the function

        PreReq
        ---
        function passed in is being called for one of its intended purposes
        '''
        # dialog_logger.debug(f"starting formatting parameters for function call. passed in: purpose <{purpose}>, a, e, g, v: <{id(active_node)}><{active_node.graph_node.id}>, <{event}>, <{goal_node}>, <{values}>")
        func_ref = self.functions[func_name]["ref"]
        intended_purposes = [x in func_ref.allowed for x in [POSSIBLE_PURPOSES.FILTER,POSSIBLE_PURPOSES.ACTION,POSSIBLE_PURPOSES.TRANSITION_FILTER,POSSIBLE_PURPOSES.TRANSITION_ACTION]]
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
            
        # dialog_logger.debug(f"sorted args list is: <{args_list}>")
        return args_list

    #NOTE: keep this function in sync with synchronous version
    async def run_func_async(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, goal_node:typing.Union[BaseType.BaseNode, str] = None, values= None):
        dialog_logger.debug(f"starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}>")
        if not self.function_is_permitted(func_name, purpose):
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                # filter functions, wether transtion or not, expect bool returns
                return False
            else:
                return None
        func_ref = self.functions[func_name]["ref"]
        dialog_logger.debug(f"runn func async found function ref <{func_ref}>")
        if inspect.iscoroutinefunction(func_ref):
            return await func_ref(*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
        return func_ref(*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
    

    #NOTE: keep this function in sync with asynchronous version
    def run_func(self, func_name:str, purpose:POSSIBLE_PURPOSES, active_node:BaseType.BaseNode, event, goal_node:typing.Union[BaseType.BaseNode, str] = None, values= None):
        dialog_logger.debug(f"starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}>")
        if not self.function_is_permitted(func_name, purpose):
            if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER]:
                return False
            else:
                return None
        return self.functions[func_name]["ref"](*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
    
    '''################################################################################################
    #
    #                                       MANAGING HANDLER DATA SECTION
    #
    ################################################################################################'''

    def get_waiting_nodes(self, event_key):
        '''gets list of active nodes waiting for certain event from handler'''
        # dev status: used, can be useful small function
        if event_key in self.event_forwarding:
            return self.event_forwarding[event_key]
        return set()
    
    '''################################################################################################
    #
    #                                       CLEANING OUT NODES SECTION
    #
    ################################################################################################'''

    async def clean_task(self, delay, prev_task):
        # keep a local reference as shared storage can be pointed to another place
        cleaning_logger.debug(f"clean task starting sleeping handler id <{id(self)}> task id <{id(self.cleaning_task)}>, task: {self.cleaning_task}")
        this_cleaning = self.cleaning_task

        # first sleep because this should only happen every x seconds
        await asyncio.sleep(delay)
        starttime = datetime.utcnow()
        if not this_cleaning:
            # last catch for task canceled in case it happened while sleeping. don't need to continue cleaning. not likely to hit this line.
            cleaning_logger.info("seems like cleaning task already cancled. handler id <%s>, task id <%s>", id(self), id(this_cleaning))
            return
        try:
            await self.clean(this_cleaning)
            #TODO: clean task smarter timing to save processing
            sleep_secs = max(0, (timedelta(seconds=self.clean_freq_secs) - (datetime.utcnow() - starttime)).total_seconds())
            # tasks are only fire once, so need to set up the next round
            self.cleaning_task = asyncio.get_event_loop().create_task(self.clean_task(sleep_secs, this_cleaning))
            cleaning_logger.debug("cleaning task <%s> set up next task call <%s>", id(this_cleaning), id(self.cleaning_task))
        except Exception as e:
            # last stop catch for exceptions just in case, otherwise will not be caught and aysncio will complain of unhandled exceptions
            execution_reporting.warning(f"error, abnormal state for handler's cleaning functions, cleaning is now stopped")
            cleaning_logger.warning("cleaning run for handler id <%s> at time <%s> failed. no more cleaning. error: <%s>", id(self), starttime, e)


    #NOTE: FOR CLEANING ALWAYS BE ON CAUTIOUS SIDE AND DO TRY EXCEPTS ESPECIALLY FOR CUSTOM HANDLING. maybe should throw out some data if that happens?
    async def clean(self, this_clean_task):
        cleaning_logger.debug("doing cleaning action. handler id <%s> task id <%s>", id(self), id(this_clean_task))
        # clean out old data from internal stores
        now = datetime.utcnow()
        timed_out_nodes = []
        for node_key, active_node in self.active_nodes.items():
            if hasattr(active_node, "timeout"):
                cleaning_logger.debug(f"checking node <{id(active_node)}> of name <{active_node.graph_node.id}> timout is <{active_node.timeout}> and should be cleaned <{active_node.timeout < now}>")
                
                if active_node.timeout is not None and active_node.timeout < now:
                    timed_out_nodes.append(active_node)

        #TODO: more defenses and handling for exceptions
        for node in timed_out_nodes:
            try:
                await self.close_node(node, timed_out=True)
            except Exception as e:
                execution_reporting.warning(f"close node failed on node {id(node)}, just going to ignore it for now")
                await self.close_node(node, timed_out=True, emergency_remove=True)

        timed_out_sessions = []
        for session in self.sessions.values():
            cleaning_logger.debug(f"checking session <{id(session)}> timout is <{session.timeout}> and should be cleaned <{session.timeout < now}>")
            if session is None:
                cleaning_logger.warning(f"found a session in abnormal state, it is None")
            elif session.timeout is not None and session.timeout < now:
                timed_out_sessions.append(session)
        
        for session in timed_out_sessions:
            try:
                await self.close_session(session, timed_out=True)
            except Exception as e:
                execution_reporting.warning(f"close session failed on session {id(session)}, just going to ignore it for now")

    def start_cleaning(self, event_loop=asyncio.get_event_loop()):
        'method to get the repeating cleaning task to start'
        self.cleaning_task = event_loop.create_task(self.clean_task(self.clean_freq_secs, None))
        cleaning_logger.info(f"starting cleaning. handler id <{id(self)}> task id <{id(self.cleaning_task)}>, <{self.cleaning_task}>")

    def stop_cleaning(self):
        cleaning_logger.info("stopping cleaning. handler id <%s> task id <%s>", id(self), id(self.cleaning_task))
        self.cleaning_task.cancel()
        self.cleaning_task = None

    def __del__(self):
        if len(self.sessions) > 0 or len(self.active_nodes) > 0:
            dialog_logger.warning(f"destrucor for handler. id'd <{id(self)}> sanity checking any memory leaks, may not be major thing \
                                  sessions left: <{self.sessions}>, nodes left: <{self.active_nodes}>")

