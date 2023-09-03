#TODO: is adding values onto fields such as event filters feasible?
#TODO: proofing against None values: what is values if you just list events flag and leave value blank, getters proofed against None, handler accesses these directly without getters so which ones might crash because of None
from datetime import datetime, timedelta

class BaseGraphNode():
    VERSION = "3.5.0"

    # this specifies what fields will be copied into graph node
    DEFINITION='''
options:
  - name: id
  - name: start
    default: Null
  - name: TTL
    default: 180
  - name: callbacks
    default: []
  - name: events
    default: {}
  - name: close_callbacks
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
    callbacks:
        type: array
        items:
            type: ["string", "object"]
    start:
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
                        callbacks:
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
                                    transition_callbacks:
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
    close_callbacks:
        type: array
        items:
            type: ["string", "object"]
required: ["id"]
    '''
    TYPE="Base"

    @classmethod
    def verify_format_data(cls, data:dict):
        '''WIP. need some way to verify data is in right format. not sure which way yet'''
        # for ind, callback in enumerate(data["callbacks"]):
        #     if isinstance(callback, str):
        #         data["callbacks"][ind] = {callback:None}

        # for event in data["events"].values():
        #     if "filters" in event:
        #         for ind, filter in enumerate(event["filters"]):
        #             if isinstance(filter, str):
        #                 event["filters"][ind] = {filter:None}
        #     if "callbacks" in event:
        #         for ind, callback in enumerate(event["callbacks"]):
        #             if isinstance(callback, str):
        #                 event["callbacks"][ind] = {callback:None}
        #     if "transitions" in event:
        #         for transition in event["transitions"]:
        #             if "transition_filters" in transition:
        #                 for ind, transition_filter in enumerate(transition["transition_filters"]):
        #                     if isinstance(transition_filter, str):
        #                         transition["transition_filters"][ind] = {transition_filter:None}
        #             if "transition_callbacks" in transition:
        #                 for ind, transition_filter in enumerate(transition["transition_callbacks"]):
        #                     if isinstance(transition_filter, str):
        #                         transition["transition_callbacks"][ind] = {transition_filter:None}
        pass

    def __init__(self, options:dict) -> None:
        self.__class__.verify_format_data(options)
        for key, option in options.items():
            setattr(self, key, option)

    def activate_node(self, session=None):
        # node_ttl = min (self.TTL) if session is None else (min(self.TTL, session.time_left().total_seconds()) if self.TTL > 0 else session.time_left().total_seconds())
        return BaseNode(self, session, timeout_duration=timedelta(seconds=self.TTL))
    
    def get_start_filters(self, event_key):
        if (self.start is not None) and (event_key in self.start) and (self.start[event_key] is not None) and ("filters" in self.start[event_key]):
            return self.start[event_key]["filters"]
        else:
            return []
        
    def get_start_callbacks(self, event_key):
        if (self.start is not None) and (event_key in self.start) and (self.start[event_key] is not None) and ("setup" in self.start[event_key]):
            return self.start[event_key]["setup"]
        else:
            return []
        
    def start_with_session(self, event_key):
        return (self.start is not None) and (event_key in self.start) and (self.start[event_key] is not None) and ("session_chaining" in self.start[event_key])
    
    def get_events(self):
        if self.events is None:
            return {}
        return self.events
    
    def get_callbacks(self):
        if self.callbacks is None:
            return []
        return self.callbacks
    
    def get_event_close_flags(self, event_key):
        if event_key in self.events and self.events[event_key] is not None and "schedule_close" in self.events[event_key]:
            close_flag = self.events[event_key]["schedule_close"]
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
        if event_key in self.events and self.events[event_key] is not None and "callbacks" in self.events[event_key]:
            return self.events[event_key]["callbacks"]
        else:
            return []
        
    def get_transitions(self, event_key):
        if event_key in self.events and self.events[event_key] is not None and "transitions" in self.events[event_key]:
            return self.events[event_key]["transitions"]
        else:
            return []
        
    def get_close_callbacks(self):
        if self.close_callbacks is None:
            return []
        return self.close_callbacks


class BaseNode():
    def __init__(self, graph_node, session=None, timeout_duration:timedelta=None) -> None:
        self.graph_node = graph_node
        self.session = session
        self.is_active = True
        self.handler = None

        self.set_TTL(timeout_duration)

    def set_TTL(self, timeout_duration=None):
        if timeout_duration is None:
            # should not really happen
            timeout_duration = timedelta(self.graph_node.TTL)

        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

    def time_left(self) -> timedelta:
        return self.timeout - datetime.utcnow()
        
    def assign_to_handler(self, handler):
        '''callback to assign handler instance to node so it can access general data. Called around time node will be added to handler 
        event tracking, but not always after added. If overriding child class, be sure to call parent'''
        #one handler per node. 
        self.handler = handler

    def close_node(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.is_active = False
        self.handler = None