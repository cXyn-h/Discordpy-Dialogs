# for better logging
import logging
import sys # needed if custom handlers. currently setup a default set for this project in LoggingHelper
import os
import src.utils.LoggingHelper as logHelper
import src.utils.SessionData as SessionData
# asyncs
import asyncio
# timed things like TTL
from datetime import datetime, timedelta
# for identifying if functions are coroutines for callbacks
import inspect
import copy

import src.DialogNodeParsing as nodeParser

import src.DialogEvents.BaseEvent as BaseEventType

import src.BuiltinFuncs.BaseFuncs as BaseFuncs

dialog_logger = logging.getLogger('Dialog Handler')
logHelper.use_default_setup(dialog_logger)
dialog_logger.setLevel(logging.INFO)

#cleaning is probably going to get really spammy so putting that in its own separate one to make debugging easier
cleaning_logger = logging.getLogger("Dialog Cleaning")
logHelper.use_default_setup(cleaning_logger)
cleaning_logger.setLevel(logging.INFO)

execution_reporting = logging.getLogger('Handler Reporting')
logHelper.use_default_setup(execution_reporting)
execution_reporting.setLevel(logging.DEBUG)

#TODO: yaml support for what events want to throw during transitions?
#TODO: allow yaml names to have scope and qualified names stuff ie parse . in names
#TODO: validation for functions parameters
#TODO: exception handling, how to direct output
#TODO: maybe fix cleaning so it doesn't stop if one node excepts? but what to do with that node that excepts when trying to stop and clear?
#TODO: sessions making sure they work as intended
#TODO: refine how nodes and sessions lifetimes interact
#TODO: create modal support
#TODO: saving and loading active nodes
#TODO: maybe transition callback functions have a transition info paramter?
#TODO: add enforcement for annotations of callbacks so can throw error when they don't match rest of yaml
#TODO: should runtime be able to affect the node settings like next node to go to, callback list etc
#TODO: Templating yaml?
#TODO: go through code fine sweep for anything that could be changing data meant to be read

class DialogHandler():
    def __init__(self, nodes=None, functions=None, settings = None, clean_freq_secs = 3, **kwargs) -> None:
        self.graph_nodes = nodes if nodes is not None else {}
        self.functions=functions if functions is not None else {}

        self.active_nodes={}
        self.event_forwarding={}

        #TODO: not relly using the session dict
        self.sessions = {}
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

    def setup_from_files(self, file_names=[]):
        '''override current graph with nodes in the passed in files. if you already read nodes from these files outside this class,
        consider passing the list of nodes into the constructor.'''
        #TODO: second pass ok and debug running
        self.graph_nodes=nodeParser.parse_files(*file_names, existing_nodes={})

    def add_nodes(self, node_list = {}):
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
    
    def add_files(self, file_names=[]):
        #TODO: second pass ok and debug running
        # note if trying to create a setting to ignore redifinition exceptions, this won't work since can't sort out redefinitions exceptions from rest
        nodeParser.parse_files(*file_names, existing_nodes=self.graph_nodes)

    def reload_files(self, file_names=[]):
        updated_nodes = nodeParser.parse_files(*file_names, existing_nodes={})
        for k, node in updated_nodes.items():
            execution_reporting.info(f"updated/created node {node.id}")
            self.graph_nodes[k] = node

    def final_validate():
        #TODO: future: function goes through all loaded dialog stuff to make sure it's valid. ie all items have required parems, 
        #       parems are right format, references point to regestered commands and dialogs, etc
        pass

    '''################################################################################################
    #
    #                                   MANAGING CALLBACK FUNCTIONS SECTION
    #
    ################################################################################################'''

    def register_function(self, func, override_settings={}):
        if hasattr(func, "allowed"):
            permitted_purposes = func.allowed
        if "allowed" in override_settings:
            permitted_purposes = override_settings["allowed"]
        
        if not permitted_purposes or len(permitted_purposes) < 1:
            execution_reporting.warning(f"dialog handler tried registering a function <{func.__name__}> that does not have any permitted sections")
            return False
        if func == self.register_function:
            execution_reporting.warning("dialog handler tried registering own registration function, dropping for security reasions")
            return False
        
        if hasattr(func,"cb_key"):
            cb_key = func.cb_key
        else:
            cb_key = func.__name__
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

    def function_is_permitted(self, func_name, section, escalate_errors=False):
        '''if function is registered in handler and is permitted to run in the given section of handling and transitioning

        Return
        ---
        False if function is not registered, false if registered and not permitted'''
        if func_name not in self.functions:
            execution_reporting.error(f"checking if <{func_name}> can run during phase <{section}> but it is not registered")
            if escalate_errors:
                raise Exception(f"checking if <{func_name}> can run during phase {section} but it is not registered")
            return False
        if section not in self.functions[func_name]["permitted_purposes"]:
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

    async def start_at(self, node_id, event_key, event):
        execution_reporting.debug(f"starting process to start at node <{node_id}> with event <{event_key}> id'd <{id(event)}> type <{type(event)}>")
        if node_id not in self.graph_nodes:
            execution_reporting.warn(f"cannot start at <{node_id}>, not valid node")
            return None
        graph_node = self.graph_nodes[node_id]
        if graph_node.start is None:
            execution_reporting.warn(f"cannot start at <{node_id}>, node settings do not allow")
            return None
        
        dialog_logger.debug(f"starting custom filter process to start <{node_id}> with event key <{event_key}> id'd <{id(event)}> oject type <{type(event)}>")
        if graph_node.start_with_session(event_key):
            session = SessionData.SessionData()
        else:
            session = None
        active_node = graph_node.activate_node(session)
        await self.run_event_callbacks_on_node(active_node, event_key, event, version="start")
        start_filters = self.run_event_filters_on_node(active_node, event_key, event, start_version=True)
        if start_filters:
            dialog_logger.info(f"starting node <{node_id}> with event key <{event_key}> id'd <{id(event)}>")
            await self.track_active_node(active_node, event)
            execution_reporting.info(f"started active version of <{node_id}>, unique id is <{id(active_node)}>")
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

    async def run_event_on_node(self, active_node, event_key, event):
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
        dialog_logger.debug(f"node >{id(active_node)}><{active_node.graph_node.id}> finished event callbacks")

        debugging_phase = "transitions"
        transition_result = await self.run_transitions_on_node(active_node,event_key,event)
        dialog_logger.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> finished transitions")

        close_flag = []
        if event_key in active_node.graph_node.get_events().keys() and active_node.graph_node.events[event_key] is not None and "schedule_close" in active_node.graph_node.events[event_key]:
            close_flag = active_node.graph_node.events[event_key]["schedule_close"]
            if isinstance(close_flag, str):
                close_flag = [close_flag]
        should_close_node = ("node" in close_flag) or transition_result[0]
        should_close_session = ("session" in close_flag) or transition_result[1]
        if should_close_node:
            debugging_phase = "closing"
            await self.close_node(active_node, timed_out=False)

        if should_close_session:
            debugging_phase = "closing session"
            execution_reporting.debug(f"node <{id(active_node)}><{active_node.graph_node.id}> event handling closing session")
            await self.close_session()
        # except Exception as e:
        #     execution_reporting.warning(f"failed to handle event on node at stage {debugging_phase}")
        #     exc_type, exc_obj, exc_tb = sys.exc_info()
        #     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #     print(exc_type, fname, exc_tb.tb_lineno)
        #     dialog_logger.info(f"exception on handling event on node <{id(active_node)}> node details: <{vars(active_node)}> exception:<{e}>")


    def run_event_filters_on_node(self, active_node, event_key, event, start_version=False):
        '''runs all filters for a node and event pair
        doesn't really need to be an async '''
        dialog_logger.debug(f"run event filters. node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, type of event <{type(event)}> filters: <{active_node.graph_node.get_event_filters(event_key)}>")
        if hasattr(event, "get_event_filters") and callable(event.get_event_filters):
            node_filters = event.get_event_filters()
        else:
            node_filters = []
        dialog_logger.debug(f"filters from node are {node_filters}")
        if start_version:
            dialog_logger.debug(f"running start version of filters on node {active_node}, start filters are {active_node.graph_node.get_start_filters(event_key)}")
            node_filters.extend(active_node.graph_node.get_start_filters(event_key))
        else:
            node_filters.extend(active_node.graph_node.get_event_filters(event_key))
        execution_reporting.debug(f"custom filter list for node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}> is <{node_filters}>")

        def running_filters_helper(handler, active_node, event, filter_list, operator="and"):
            for filter in filter_list:
                # dialog_logger.debug(f"testing recursive helper, at filter {filter} in list {filter_list}")
                if isinstance(filter, str):
                    # filter_run_result = run_filter(handler, filter, active_node, event, None)
                    filter_run_result = self.run_func(filter, "filter", active_node, event)
                else:
                    # is a dict representing function call with arguments or nested operator, should only have one key
                    key = list(filter.keys())[0]
                    value = filter[key]
                    if key in ["and", "or"]:
                        filter_run_result = running_filters_helper(handler, active_node, event, value, operator=key)
                    else:
                        # argument in vlaue is expected to be one object. a list, a dict, a string etc
                        # filter_run_result = run_filter(handler, key, active_node, event, value)
                        filter_run_result = self.run_func(key, "filter", active_node, event, values=value)
                # early break because not possible to change result with rest of list
                if operator == "and" and not filter_run_result:
                    return False
                if operator == "or" and filter_run_result:
                    return True
            # end of for loop, means faild to find early break point
            if operator == "and":
                return True
            if operator == "or":
                return False
        try:
            return running_filters_helper(self, active_node, event, node_filters)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run filters on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")
            return False
    

    async def run_event_callbacks_on_node(self, active_node, event_key, event, version = None):
        '''runs all callbacks for a node event pair
        
        Parameters:
        ---
        closing_version - `str`
            "start", "close", or None'''
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
            for callback in callbacks:
                if isinstance(callback, str):
                    await self.run_func_async(callback, "callback", active_node, event)
                else:
                    key = list(callback.keys())[0]
                    value = callback[key]
                    await self.run_func_async(key, "callback", active_node, event, values=value)
        except Exception as e:
            execution_reporting.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>. assuming skip")
            dialog_logger.error(f"exception happened when trying to run callbacks on node <{id(active_node)}><{active_node.graph_node.id}>, event key <{event_key}>, details {e}")


    async def run_transitions_on_node(self, active_node, event_key, event):
        '''handles going through transition to new node (not including closing current one if needed) for one node and event pair'''

        def transition_filter_helper(handler, active_node, event, goal_node, filter_list, operator="and"):
            for filter in filter_list:
                # dialog_logger.debug(f"testing recursive helper, at filter {filter} in list {filter_list}")
                if isinstance(filter, str):
                    filter_run_result = self.run_func(filter, "transition_filter", active_node, event, goal_node)
                else:
                    # is a dict representing function call with arguments or nested operator, should only have one key
                    key = list(filter.keys())[0]
                    value = filter[key]
                    if key in ["and", "or"]:
                        filter_run_result = transition_filter_helper(handler, active_node, event, goal_node, value, operator=key)
                    else:
                        # argument in vlaue is expected to be one object. a list, a dict, a string etc
                        filter_run_result = self.run_func(key, "transition_filter", active_node, event, goal_node, value)
                # early break because not possible to change result with rest of list
                if operator == "and" and not filter_run_result:
                    return False
                if operator == "or" and filter_run_result:
                    return True
            # end of for loop, means faild to find early break point
            if operator == "and":
                return True
            if operator == "or":
                return False

        dialog_logger.debug(f"handling transitions for node <{id(active_node)}><{active_node.graph_node.id}>")
        node_transitions = active_node.graph_node.get_transitions(event_key)
        passed_transitions = []
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
                        filter_res = transition_filter_helper(self, active_node, event, node_name, transition["transition_filters"])
                        if isinstance(filter_res, bool) and filter_res:
                            passed_transitions.append((node_name, transition["transition_callbacks"] if "transition_callbacks" in transition else [],
                                                        transition["session_chaining"] if "session_chaining" in transition else "end", close_flag))
                    except Exception as e:
                        execution_reporting.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}>. assuming skip")
                        dialog_logger.error(f"exception happened when trying to filter transitions from node <{id(active_node)}><{active_node.graph_node.id}> to <{node_name}>, details {e}")
                else:
                    passed_transitions.append((node_name, transition["transition_callbacks"] if "transition_callbacks" in transition else [],
                                               transition["session_chaining"] if "session_chaining" in transition else "end", close_flag))

        dialog_logger.debug(f"transitions that passed filters are for nodes <{[x[0] for x in passed_transitions]}>")

        #TODO: ordering gauranttes for order of transitions processed? technically a node with multiple transitions, 
        #   when running transition callbacks the node data for the next transitions can be different from previous
        directives = [False, False]
        for passed_transition in passed_transitions:
            execution_reporting.info(f"doing transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{passed_transition[0]}> callbacks are <{passed_transition[1]}>")
            session = active_node.session
            if passed_transition[2] == "start" or (passed_transition[2] == "chain" and active_node.session is None):
                dialog_logger.info(f"starting session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{passed_transition[0]}>")
                #TODO: allow yaml specify timeout for sessions?
                session = SessionData.SessionData()
                self.register_session(session)
                dialog_logger.debug(f"session debugging, started new session, id is <{id(session)}>")

            if passed_transition[2] == "section" and session is not None:
                await self.clear_session_history(session)

            next_node = self.graph_nodes[passed_transition[0]].activate_node(session)
            execution_reporting.info(f"activated next node, is of graph node <{passed_transition[0]}>, id'd <{id(next_node)}>")
            if passed_transition[2] != "end" and session is not None:
                dialog_logger.info(f"adding next node to session for transition from node id'd <{id(active_node)}><{active_node.graph_node.id}> to goal <{passed_transition[0]}>")
                session.add_node(next_node)
                dialog_logger.info(f"session debugging, session being chained. id <{id(session)}>, adding node <{id(next_node)}><{next_node.graph_node.id}> to it, now node list is <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
                
            for callback in passed_transition[1]:
                if isinstance(callback, str):
                    await self.run_func_async(callback, "transition_callback", active_node, event, next_node)
                else:
                    key = list(callback.keys())[0]
                    value = callback[key]
                    await self.run_func_async(key, "transition_callback", active_node, event, next_node, values=value)

            # dialog_logger.info(f"checking session data, {session}")

            close_flag = passed_transition[3]
            directives[0] = directives[0] or ("node" in close_flag)
            directives[1] = directives[1] or ("session" in close_flag)
            await self.track_active_node(next_node, event)
        return directives
    
    '''################################################################################################
    #
    #                   I-DONT-REALLY-HAVE-A-NAME-BUT-IT-DOESNT-FIT-ELSEWHERE SECTION
    #
    ################################################################################################'''

    async def track_active_node(self, active_node, event):
        #TODO: fine tune id for active nodes
        dialog_logger.info(f"adding node <{id(active_node)}><{active_node.graph_node.id}> to internal tracking")
        self.active_nodes[id(active_node)] = active_node
        #TODO: discord example depends on this function being called before callbacks are. either find another way to pass bot reference to callbacks
        #   or revisit whether or not I want this strictly called after officially being added and if that only happens after callbacks
        active_node.added_to_handler(self)

        for callback in active_node.graph_node.callbacks:
            if isinstance(callback, str):
                await self.run_func_async(callback, "callback", active_node, event)
            else:
                key = list(callback.keys())[0]
                value = callback[key]
                await self.run_func_async(key, "callback", active_node, event, values=value)

        for listed_event in active_node.graph_node.get_events().keys():
            if listed_event not in self.event_forwarding:
                self.event_forwarding[listed_event] = set()
            self.event_forwarding[listed_event].add(active_node)
        
        # is autoremoval if not waiting for anything, but found there might be cases where want to keep node around
        # if len(active_node.graph_node.get_events()) < 1:
        #     await self.close_node(active_node, timed_out=False)


    async def close_node(self, active_node, timed_out=False, emergency_remove = False):
        execution_reporting.info(f"closing node <{id(active_node)}><{active_node.graph_node.id}> timed out? <{timed_out}>")
        if not emergency_remove:
            await self.run_event_callbacks_on_node(active_node, "close", {"timed_out":timed_out}, version=True)

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

        if id(active_node) in self.active_nodes:
            del self.active_nodes[id(active_node)]
        for event in active_node.graph_node.get_events().keys():
            if event is not None and event in self.event_forwarding:
                self.event_forwarding[event].remove(active_node)

    def register_session(self, session):
        self.sessions[id(session)] = session
    
    async def clear_session_history(self, session):
        for node in session.get_linked_nodes():
            if node.is_active:
                await self.close_node(node, timed_out=True)
        session.clear_session_history()
    
    async def close_session(self, session):
        execution_reporting.debug(f"closing session <{id(session)}>, current nodes <{[str(id(x))+ ' ' +x.graph_node.id for x in session.get_linked_nodes()]}>")
        await self.clear_session_history(session)
        del self.sessions[id(session)]
        pass

    '''################################################################################################
    #
    #                                       FUNCTION CALLBACK HELPERS SECTION
    #
    ################################################################################################'''

    def format_parameters(self, func_name, purpose, active_node, event, goal_node = None, values = None):
        '''
        Takes information that is meant to be passed to custom filter/callback functions and gets the parameters in the right order to be passed.
        parameters will be passed in this order: the active node instance, the event that happened to node, the next node name if transition filter or active
        next node if transition callback otherwise nothing here, and then if it exists any extra arguments to the function

        PreReq
        ---
        function passed in is being called for one of its intended purposes
        '''
        func_ref = self.functions[func_name]["ref"]
        intended_purposes = [x in self.functions[func_name]["permitted_purposes"] for x in ["filter","callback","transition_filter","transition_callback"]]
        cross_transtion = (intended_purposes[2] or intended_purposes[3]) and (intended_purposes[0] or intended_purposes[1])

        args_list = [active_node,event]
        spec = inspect.getfullargspec(func_ref)
        if cross_transtion and len(spec[0]) == 4 and spec[3] is not None and len(spec[3]) < 2:
            # if can do transition and non-transition, and function has four parameters and only one is optional
            # if can do both transition and non-transitional, goal node parameter has to be optional
            # in this case only having one optional parameter means the arguments to the function is required.
            # ordering is values are passed last, so if that is required, then it and goal need to be swapped
            if values is None:
                raise Exception(f"missing arguments to pass to function {func_name}")
            args_list.append(values)
            if purpose in ["transition_filter", "transition_callback"]:
                if goal_node is None:
                    raise Exception(f"trying to call {func_name} but is missing required goal node")
                args_list.append(goal_node)
            return args_list
        
        if purpose in ["transition_filter", "transition_callback"]:
            # function is getting called for handling transition
            if goal_node is None:
                raise Exception(f"trying to call {func_name} for a transition but are missing goal node")
            args_list.append(goal_node)
        elif cross_transtion:
            # if calling for non-transitional, function can still be one that accepts both, so thats why there's this if check
            # if function can take both goal node field is optional
            args_list.append(None)

        if values is not None:
            if len(spec[0]) == len(args_list):
                execution_reporting.warning(f"calling {func_name}, have extra value for function parameters, discarding")
            else:
                args_list.append(values)
        return args_list

    #NOTE: keep this function in sync with synchronous version
    async def run_func_async(self, func_name, purpose, active_node, event, goal_node = None, values= None):
        dialog_logger.debug(f"starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}>")
        if not self.function_is_permitted(func_name, purpose):
            if "filter" in purpose:
                # filter functions, wether transtion or not, expect bool returns
                return False
            else:
                return None
        func_ref = self.functions[func_name]["ref"]
        if inspect.iscoroutinefunction(func_ref):
            return await self.functions[func_name]["ref"](*self.format_parameters(func_name, purpose, active_node, event, goal_node, copy.deepcopy(values)))
        return self.functions[func_name]["ref"](*self.format_parameters(func_name, purpose,active_node, event, goal_node, copy.deepcopy(values)))
    

    #NOTE: keep this function in sync with asynchronous version
    def run_func(self, func_name, purpose, active_node, event, goal_node=None, values=None):
        dialog_logger.debug(f"starting running function named <{func_name}> for node <{id(active_node)}><{active_node.graph_node.id}> section <{purpose}>")
        if not self.function_is_permitted(func_name, purpose):
            if "filter" in purpose:
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
            if session.timeout < now:
                timed_out_sessions.append(session)
        
        for session in timed_out_sessions:
            try:
                await self.close_session(session)
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

