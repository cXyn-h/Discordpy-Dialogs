#TODO: is adding values onto fields such as event filters feasible?
#TODO: proofing against None values: what is values if you just list events flag and leave value blank, getters proofed against None, handler accesses these directly without getters so which ones might crash because of None
from datetime import datetime, timedelta
import typing
import src.utils.SessionData as SessionData
import yaml
import copy
from src.utils.Enums import POSSIBLE_PURPOSES, ITEM_STATUS

import src.utils.Cache as Cache

class BaseGraphNode(Cache.AbstractCacheEntry):
    VERSION = "3.6.0"
    # this specifies what fields will be copied into graph node
    DEFINITION='''
options:
  - name: id
  - name: graph_start
    default: Null
  - name: TTL
    default: 180
  - name: actions
    default: []
  - name: events
    default: {}
  - name: close_actions
    default: []
'''
    SCHEMA='''
type: object
patternProperties:
    "^v(ersion)?$":
        type: "string"
        pattern: '[0-9]+\.[0-9]+\.[0-9]+'
properties:
    id: 
        type: "string"
    type:
        type: "string"
    actions:
        type: array
        items:
            type: ["string", "object"]
    graph_start:
        type: object
        patternProperties:
            ".+":
                anyOf:
                    - type: "null"
                    - type: "object"
                      properties:
                        filters:
                            type: array
                            items:
                                type: ["string", "object"]
                        session_chaining:
                            enum: ["start"]
                        setup:
                            type: array
                            items:
                                type: ["string", "object"]
                      unevaluatedProperties: false
        unevaluatedProperties: false
    events:
        type: object
        patternProperties:
            ".+":
                anyOf:
                    - type: "null"
                    - type: "object"
                      properties:
                        filters:
                            type: array
                            items:
                                type: ["string", "object"]
                        actions:
                            type: array
                            items:
                                type: ["string", "object"]
                        schedule_close:
                            anyOf:
                                - enum: ["node", "session"]
                                - type: "array"
                                  items:
                                    enum: ["node", "session"]
                        transitions:
                            type: array
                            items:
                                type: object
                                properties:
                                    node_names:
                                        anyOf:
                                            - type: "string"
                                            - type: "array"
                                              items:
                                                type: "string"
                                    transition_filters:
                                        type: array
                                        items:
                                            type: ["string", "object"]
                                    transition_actions:
                                        type: array
                                        items:
                                            type: ["string", "object"]
                                    schedule_close:
                                        anyOf:
                                            - enum: ["node", "session"]
                                            - type: "array"
                                              items:
                                                enum: ["node", "session"]
                                    session_chaining:
                                        enum: ["start", "chain", "section"]
                                required: [node_names]
                      unevaluatedProperties: false
        unevaluatedProperties: false
    TTL: 
        type: integer
        minimum: -1
    close_actions:
        type: array
        items:
            type: ["string", "object"]
required: ["id"]
    '''
    TYPE="Base"

    def validate_node(self):
        unique_next_nodes = set()
        function_set_list = []
        if self.graph_start is not None:
            for event_type, settings in self.graph_start.items():
                if settings is None:
                    continue
                if "setup" in settings:
                    function_set_list.append((settings["setup"], self.id, POSSIBLE_PURPOSES.ACTION, "graph start setup", event_type))
                if "filters" in settings:
                    function_set_list.append((settings["filters"], self.id, POSSIBLE_PURPOSES.FILTER, "graph start filters", event_type))
        function_set_list.append((self.actions, self.id, POSSIBLE_PURPOSES.ACTION, "node enter actions"))
        for event_type, settings in self.events.items():
            if "filters" in settings:
                function_set_list.append((settings["filters"], self.id, POSSIBLE_PURPOSES.FILTER, f"node {event_type} event filters", event_type))
            if "actions" in settings:
                function_set_list.append((settings["actions"], self.id, POSSIBLE_PURPOSES.ACTION, f"node {event_type} event actions", event_type))
            if "transitions" in settings:
                for transition_num, transition_settings in enumerate(settings["transitions"]):
                    if type(transition_settings["node_names"]) is str:
                        unique_next_nodes.add(transition_settings["node_names"])
                    else:
                        for next_node in transition_settings["node_names"]:
                            unique_next_nodes.add(next_node)
                    if "transition_filters" in transition_settings:
                        function_set_list.append((transition_settings["transition_filters"],  self.id, POSSIBLE_PURPOSES.TRANSITION_FILTER, f"node {event_type} event  index {transition_num} transition filters", event_type))
                    if "transition_actions" in transition_settings:
                        function_set_list.append((transition_settings["transition_actions"], self.id, POSSIBLE_PURPOSES.TRANSITION_ACTION, f"node {event_type} event index {transition_num} transition actions", event_type))
        return unique_next_nodes, function_set_list

    def __init__(self, options:dict) -> None:
        super().__init__(id(self), timeout=-1)
        for key, option in options.items():
            setattr(self, key, option)

    def activate_node(self, session:typing.Union[None, SessionData.SessionData]=None) -> "BaseNode":
        '''creates and sets up an active node based on this graph node'''
        # node_ttl = min (self.TTL) if session is None else (min(self.TTL, session.time_left().total_seconds()) if self.TTL > 0 else session.time_left().total_seconds())
        return BaseNode(self, session, timeout_duration=timedelta(seconds=self.TTL))
    
    def can_start(self, event_key:str):
        if self.graph_start is None:
            return False
        return event_key in self.graph_start
    
    def get_start_filters(self, event_key:str):
        if self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("filters" in self.graph_start[event_key]):
            return self.graph_start[event_key]["filters"]
        else:
            return []
        
    def get_start_callbacks(self, event_key:str):
        if self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("setup" in self.graph_start[event_key]):
            return self.graph_start[event_key]["setup"]
        else:
            return []
        
    def starts_with_session(self, event_key:str):
        return self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("session_chaining" in self.graph_start[event_key])
    
    def get_events(self):
        if self.events is None:
            return {}
        return self.events
    
    def get_callbacks(self):
        if self.actions is None:
            return []
        return self.actions
    
    def get_event_close_flags(self, event_key:str):
        if event_key in self.events.keys() and self.events[event_key] is not None and "schedule_close" in self.events[event_key]:
            close_flag:typing.Union[str, list[str]] = self.events[event_key]["schedule_close"]
            if isinstance(close_flag, str):
                return [close_flag]
            else:
                return close_flag
        return []
    
    def get_event_filters(self, event_key):
        if event_key in self.events and self.events[event_key] is not None and "filters" in self.events[event_key]:
            return self.events[event_key]["filters"]
        else:
            return []
        
    def get_event_callbacks(self, event_key):
        if event_key in self.events and self.events[event_key] is not None and "actions" in self.events[event_key]:
            return self.events[event_key]["actions"]
        else:
            return []
        
    def get_transitions(self, event_key):
        if event_key in self.events and self.events[event_key] is not None and "transitions" in self.events[event_key]:
            return self.events[event_key]["transitions"]
        else:
            return []
        
    def get_close_callbacks(self):
        if self.close_actions is None:
            return []
        return self.close_actions
    
    @classmethod
    def get_node_fields(cls):
        '''merges together the config and inherited config for what fields active nodes of this type should have and caches and returns it.
        Child classes override parents' fields'''
        # note, hasattr uses getattr which default also looks in parent classes, which sensibly also applies to class variables. don't use it for something that needs to be defined per class independent of parents'
        if "PARSED_DEFINITION" in vars(cls).keys() and cls.PARSED_DEFINITION is not None:
            # if there's a previous result of parsed definition cached, use that
            return cls.PARSED_DEFINITION
        # nothing cached, need to actually find definitions for this class
        mro_list = cls.__mro__
        final_definitions = {}
        parent_definitions = mro_list[1].get_node_fields() if len(mro_list) > 1 and hasattr(mro_list[1], "get_node_fields") else {}
        for option in parent_definitions:
            final_definitions[option["name"]] = copy.deepcopy(option)

        self_modifications = yaml.safe_load(cls.DEFINITION)
        for option in self_modifications["options"]:
            final_definitions[option["name"]] = option

        cls.PARSED_DEFINITION = list(final_definitions.values())
        return list(final_definitions.values())
    
    @classmethod
    def get_node_schema(cls):
        #TODO: probably need something to merge schemas, this will treat the two as independent, and can't use child classes to override base schema
        if "PARSED_SCHEMA" in vars(cls).keys() and cls.PARSED_SCHEMA is not None:
            # if there's a previous result of parsed schema cached, use that
            return cls.PARSED_SCHEMA
        mro_list = cls.__mro__
        final_schema = mro_list[1].get_node_schema() if len(mro_list) > 1 and hasattr(mro_list[1], "get_node_schema") else {"allOf": []}

        self_schema = yaml.safe_load(cls.SCHEMA)
        final_schema["allOf"].append(self_schema)
        cls.PARSED_SCHEMA = final_schema
        return copy.deepcopy(final_schema)


class BaseNode(Cache.AbstractCacheEntry):
    def __init__(self, graph_node:BaseGraphNode, session:typing.Union[None, SessionData.SessionData]=None, timeout_duration:timedelta=None) -> None:
        super().__init__(id(self), timeout = timeout_duration.total_seconds() if timeout_duration else -1)
        self.graph_node = graph_node
        self.session = session
        self.status = ITEM_STATUS.INACTIVE
        self.handler = None

    def time_left(self) -> timedelta:
        return self.timeout - datetime.utcnow()
        
    def assign_to_handler(self, handler):
        '''callback to assign handler instance to node so it can access general data. Called around time node will be added to handler 
        event tracking, but not always after added. If overriding in child class, be sure to call parent'''
        #one handler per node. 
        self.handler = handler
        self.activate()

    def activate(self):
        self.status = ITEM_STATUS.ACTIVE

    def is_active(self):
        return self.status == ITEM_STATUS.ACTIVE

    def notify_closing(self):
        self.status = ITEM_STATUS.CLOSING

    def close(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.status = ITEM_STATUS.CLOSED
        self.handler = None