#TODO: is adding values onto fields such as event filters feasible?
#TODO: proofing against None values: what is values if you just list events flag and leave value blank, getters proofed against None, handler accesses these directly without getters so which ones might crash because of None
from datetime import datetime, timedelta

class GraphNode():
    VERSION = "3.5.0"
    #TODO: maybe merge this with Schema? need some way to query for default values in schema
    DEFINITION='''
options:
  - name: id
    presence: required
  - name: start
    presence: optional
    default: Null
  - name: TTL
    presence: optional
    default: 180
  - name: callbacks
    presence: optional
    default: []
  - name: events
    presence: optional
    default: {}
  - name: close_callbacks
    presence: optional
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
                                        enum: ["start", "end", "chain"]
                                required: [node_names]
                      unevaluatedProperties: false
        unevaluatedProperties: false
    TTL: 
        type: integer
    close_callbacks:
        type: array
        items:
            type: ["string", "object"]
required: ["id"]
    '''
    TYPE="Base"

    @classmethod
    def verify_format_data(cls, data):
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

    def __init__(self, options) -> None:
        for key, option in options.items():
            setattr(self, key, option)

    def activate_node(self, session=None):
        return Node(self, session, timeout_duration=timedelta(seconds=self.TTL))
    
    def get_start_filters(self, event_key):
        if (self.start is not None) and (event_key in self.start) and (self.start[event_key] is not None) and ("filters" in self.start[event_key]):
            return self.start[event_key]["filters"]
        else:
            return []
    
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


class Node():
    def __init__(self, graph_node, session=None, timeout_duration:timedelta=None) -> None:
        self.graph_node = graph_node
        self.session = session
        self.is_active = True
        self.handler = None

        if self.graph_node.TTL == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            if timeout_duration == None:
                # should never happen anyways
                timeout_duration=timedelta(seconds=self.graph_node.TTL)
            self.timeout = datetime.utcnow() + timeout_duration
        
    def added_to_handler(self, handler):
        '''callback for when node is now being tracked by a handler that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        #one handler per node. 
        self.handler = handler

    def close_node(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.is_active = False
        self.handler = None