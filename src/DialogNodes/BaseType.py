#TODO: is adding values onto fields such as event filters feasible?
#TODO: proofing against None values: what is values if you just list events flag and leave value blank, getters proofed against None, handler accesses these directly without getters so which ones might crash because of None
#TODO: double check if inherited from parent class's set and update methods should be used (probably, but further down pipeline problem)
from datetime import datetime, timedelta
import typing
import src.utils.SessionData as SessionData
import yaml
import copy
from src.utils.Enums import POSSIBLE_PURPOSES, ITEM_STATUS

import src.utils.Cache as Cache

class BaseGraphNode:
    VERSION = "3.8.0"
    # this specifies what fields will be copied into graph node
    FIELDS='''
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
properties:
    version: 
        type: "string"
        pattern: '[0-9]+\.[0-9]+\.[0-9]+'
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
                            oneOf:
                                - enum: ["start"]
                                - type: object
                                  properties:
                                    start:
                                        type: number
                                        minimum: -1
                                  additionalProperties: False
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
                                            - type: object
                                              patternProperties:
                                                ".+":
                                                    type: integer
                                                    minimun: 1
                                                    additionalProperties: False
                                            - type: "array"
                                              items:
                                                anyOf:
                                                    - type: "string"
                                                    - type: object
                                                      patternProperties:
                                                        ".+":
                                                          type: integer
                                                          minimun: 1
                                                          additionalProperties: False
                                    transition_counters:
                                        type: array
                                        items:
                                            type: ["string", "object"]
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
                                        oneOf:
                                            - enum: ["start", "chain", "section"]
                                            - type: object
                                              properties:
                                                start:
                                                  type: number
                                                  minimum: -1
                                              additionalProperties: False
                                            - type: object
                                              properties:
                                                chain:
                                                  type: number
                                                  minimum: -1
                                              additionalProperties: False
                                            - type: object
                                              properties:
                                                section:
                                                  type: number
                                                  minimum: -1
                                              additionalProperties: False
                                required: [node_names]
                      unevaluatedProperties: false
        unevaluatedProperties: false
    TTL: 
        type: number
        minimum: -1
    close_actions:
        type: array
        items:
            type: ["string", "object"]
required: ["id"]
    '''
    TYPE="Base"

    def validate_node(self):
        #TODO: feels clunkly. reevaluate what does need to be validated here (probably at least a way to check if functions needed and nodes to go to are actually in handler)
        #  (what about the rest of node definition? think it should have been validated on edits)
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
                    next_nodes_count = BaseGraphNode.parse_node_names(transition_settings["node_names"])
                    for next_node in next_nodes_count:
                        unique_next_nodes.add(next_node)
                    if "tansition_counters" in transition_settings:
                        function_set_list.append((transition_settings["transition_counters"],  self.id, POSSIBLE_PURPOSES.TRANSITION_COUNTER, f"node {event_type} event  index {transition_num} transition counters", event_type))
                    if "transition_filters" in transition_settings:
                        function_set_list.append((transition_settings["transition_filters"],  self.id, POSSIBLE_PURPOSES.TRANSITION_FILTER, f"node {event_type} event  index {transition_num} transition filters", event_type))
                    if "transition_actions" in transition_settings:
                        function_set_list.append((transition_settings["transition_actions"], self.id, POSSIBLE_PURPOSES.TRANSITION_ACTION, f"node {event_type} event index {transition_num} transition actions", event_type))
        return unique_next_nodes, function_set_list

    def __init__(self, options:dict) -> None:
        '''Instances hold specific settings for one graph node. 
        
        Init Parameters
        ---
        * options - `dict`
            All options defined in the GraphNode class will be added as dot notation referencable fields on each GraphNode object.
            this parameter is a ditionary option name to values for the fields of this object.
            Makes sure all and only all fields listed in Graph node type's class are defined. values that are not primitives should be copied before passing in.
            On missing values, tries to use defaults from class.FIELDS, otherwise raises an exception. Ignores extras.
        '''
        # need to get data for all fields that need to exist for node, so get list of all fields and their defaults and go through 
        # passed in list for this instance's values
        # keeping track of missing fields
        options_missing = []
        for field in self.__class__.get_node_fields():
            field_name = field["name"]
            if field_name in options:
                setattr(self, field_name, options[field_name])
            elif "default" in field:
                setattr(self, field_name, copy.deepcopy(field["default"]))
            else:
                options_missing.append(field_name)
        
        # assuming all options found from getting node fields are required, so no default and nothing specified in passed in definition means fail
        if len(options_missing) > 0:
            raise Exception(f"node object of type {self.__class__.__name__} missing values for fields during init: {options_missing}")
        
        self.set_TTL(timeout_duration=timedelta(seconds=-1))

    def set_TTL(self, timeout_duration:timedelta):
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

    def activate_node(self, session:typing.Union[None, SessionData.SessionData]=None) -> "BaseNode":
        '''creates and returns an active Node of the GraphNode's type. if there's a passed in session object, ties the created active node to the session'''
        # node_ttl = min (self.TTL) if session is None else (min(self.TTL, session.time_left().total_seconds()) if self.TTL > 0 else session.time_left().total_seconds())
        return BaseNode(self, session, timeout_duration=timedelta(seconds=self.TTL))
    
    def can_start(self, event_key:str):
        '''checks whether or not event of event_key is allowed to start at this node. Must have event's key listed within graph_start section to be allowed to start'''
        if self.graph_start is None:
            return False
        return event_key in self.graph_start
        
    def starts_with_session(self, event_key:str):
        '''checks if the given event requires setting up a session when starting this node.'''
        return self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("session_chaining" in self.graph_start[event_key])
    
    def get_start_session_TTL(self, event_key:str):
        if self.starts_with_session(event_key):
            if not isinstance(self.graph_start[event_key]["session_chaining"], str):
                duration = float(self.graph_start[event_key]["session_chaining"]["start"])
                if duration < -1:
                    duration = -1
                return duration
            else: 
                return None
        return None
    
    def get_start_callbacks(self, event_key:str):
        '''returns a list of function names needed for performing startup actions for the given event_key. startup actions are not required, so will return an empty list if none are listed'''
        if self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("setup" in self.graph_start[event_key]):
            #TODO: verify if can return a copy instead, should be copyable? also verify all these functions returning in stored format is ok or not
            return self.graph_start[event_key]["setup"]
        else:
            return []

    def get_start_filters(self, event_key:str):
        '''returns a list of function names needed for filtering starting with this event_key. Filters aren't required, and will return empty list if none are listed'''
        if self.can_start(event_key) and (self.graph_start[event_key] is not None) and ("filters" in self.graph_start[event_key]):
            return self.graph_start[event_key]["filters"]
        else:
            return []
    
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
    def parse_node_names(cls, node_names):
        '''helper for parsing a given node name found in transition section of node definition. value can be a string for one copy of one node, a dictionary for any number
        of any group of nodes, or a list to combine the two. each name should only appear once in one transition, if it appears multiple this does not add the amounts it overrides
        
        returns
        ---
        a dictionary of node name found to count of how many instances to create
        '''
        node_name_list = {}
        if isinstance(node_names, str):
            node_name_list[node_names] = 1
        elif isinstance(node_names, dict):
            node_name_list.update(node_names)
        else:
            for item in node_names:
                returned = cls.parse_node_names(item)
                node_name_list.update(returned)
        return node_name_list
    
    @classmethod
    def get_node_fields(cls):
        '''method that finds all the fields that a GraphNode of this type should have. This is done by merging together inherited field definitions and this class's.
        Child classes override parents' fields.
        Result is a list of dictionaries of all fields and their settings.
        Caches result in GraphNode class, and returns a separate copy of result'''
        # note, hasattr uses getattr which default also looks in parent classes, which sensibly also applies to class variables.
        #   don't use it for something that needs to be defined per class independent of parents'
        if "PARSED_FIELDS" in vars(cls).keys() and cls.PARSED_FIELDS is not None:
            # if there's a previous result of parsed definition cached, use that
            return copy.deepcopy(cls.PARSED_FIELDS)

        # nothing cached, need to actually find definitions for this class
        # grab inherited fields first
        mro_list = cls.__mro__
        final_definitions = {}
        # hoping any non-node classes in this mro list will not have get_node_fields function (not checking isinstance so duck typing can work)
        if len(mro_list) > 1:
            # if longer than one means there's inheritance and need to gather all fields inherited from nodes
            # for loop takes off the zero-th element cause that is self
            for parent in reversed(mro_list[1:]):
                parent_definitions = parent.get_node_fields() if hasattr(parent, "get_node_fields") else {}
                # convert the returned list into a dict that's being used for easy finding
                for single_field in parent_definitions:
                    final_definitions[single_field["name"]] = copy.deepcopy(single_field)

        # load self definitions on top
        self_modifications = yaml.safe_load(cls.FIELDS)
        if self_modifications is None:
            # this class doesn't have any fields to add, only base type cannot be allowed to do this
            if cls.__name__ == BaseGraphNode.__name__:
                raise Exception("Base type fields definition is critically malformed. whole system canot be used.")
            cls.PARSED_FIELDS = list(final_definitions.values())
            return list(final_definitions.values())
        if not isinstance(self_modifications, dict) or "options" not in self_modifications or self_modifications["options"] is None:
            raise Exception(f"node type <{cls.TYPE}> has badly formed fields. Must be either empty or have a list of fields in yaml format")
        # this class does have fields to add
        for single_field in self_modifications["options"]:
            if "name" not in single_field:
                raise Exception(f"node type <{cls.TYPE}> has malformed option: An option in definition is missing a name")
            if single_field["name"] in final_definitions:
                final_definitions.update({single_field["name"]: single_field})
            else:
                final_definitions[single_field["name"]] = single_field

        cls.PARSED_FIELDS = list(final_definitions.values())
        return list(final_definitions.values())
    
    @classmethod
    def get_node_schema(cls):
        #TODO: probably need something to merge schemas, this will treat the two as independent, and can't use child classes to override base schema
        if "PARSED_SCHEMA" in vars(cls).keys() and cls.PARSED_SCHEMA is not None:
            # if there's a previous result of parsed schema cached, use that
            return copy.deepcopy(cls.PARSED_SCHEMA)

        mro_list = cls.__mro__
        #TODO: this technically works for multi inheritance, but easily multiplies the length. maybe do something to find and merge duplicates later
        final_schema = {"allOf": []}
        # hoping any non-node classes in this mro list will not have get_node_schema function (not checking isinstance so duck typing can work)
        if len(mro_list) > 1:
            # if longer than one means there's inheritance and need to gather all schema details inherited from nodes
            # for loop takes off the zero-th element cause that is self
            for parent in reversed(mro_list[1:]):
                parent_definitions = parent.get_node_schema() if hasattr(parent, "get_node_schema") else {"allOf": []}
                for schema_fragment in parent_definitions["allOf"]:
                    final_schema["allOf"].append(schema_fragment)

        # load self schema on top
        self_schema = yaml.safe_load(cls.SCHEMA)
        if self_schema is None:
            # this class doesn't have any schema to add, only base type cannot be allowed to do this
            if cls.__name__ == BaseGraphNode.__name__:
                raise Exception("Base type schema is critically malformed. whole system canot be used.")
            cls.PARSED_SCHEMA = final_schema
            return copy.deepcopy(final_schema)
        if not isinstance(self_schema, dict):
            raise Exception(f"node type <{cls.TYPE}> seems to have badly formed schema.")
        final_schema["allOf"].append(self_schema)
        cls.PARSED_SCHEMA = final_schema
        return copy.deepcopy(final_schema)
    
    @classmethod
    def get_version(cls):
        return cls.VERSION
    
    @classmethod
    def check_version_compatibility(cls, other_version):
        result_warning_message = ""
        def parse_version_string(version_string):
            '''
            Return
            ---
            Optional[tuple]
            '''
            first_dot=version_string.find(".")
            if first_dot < 0:
                return None
            second_dot=version_string.find(".",first_dot+1)
            if second_dot < 0:
                return None
            try:
                version_tuple=(int(version_string[:first_dot]),int(version_string[first_dot+1:second_dot]), int(version_string[second_dot+1:]))
            except:
                return None
            if version_tuple[0] < 0 or version_tuple[1] < 0 or version_tuple[2] < 0:
                return None
            return version_tuple

        if not other_version:
            other_version = cls.get_version()
            result_warning_message += f"no version given, assuming most recent of '{other_version}'. might break if not compatible.\n"

        other_version_values = parse_version_string(other_version)
        this_version_values = parse_version_string(cls.get_version())

        if this_version_values is None:
            return False, "loaded node definition has badly formatted version, developer needs to fix.\n"
        if other_version_values is None:
            return False, "version given is badly formatted. must be three period separated whole numbers\n"

        if other_version_values[0] != this_version_values[0]:
            return False, f"loaded node definition cannot handle version given {other_version}"
        if other_version_values[1] != this_version_values[1]:
            return True, f"loaded node definition can handle version {other_version}, though it would be best to match." +\
                ' node config seems lilke its on an older version, please be sure to update node config to match current loaded of '+cls.get_version() \
                if other_version_values[1] < this_version_values[1] else ""
        else:
            return True, ""
    
    @classmethod
    def compare_version(cls, other_version):
        '''
        compares the loaded definition's version to the given other version string.
        
        Return
        ---
        None if could not compare the versions, which can be because one of the version strings is invalid or not able to be conpared
        the largest '''
        def parse_version_string(version_string):
            '''
            Return
            ---
            Optional[tuple]
            '''
            first_dot=version_string.find(".")
            if first_dot < 0:
                return None
            second_dot=version_string.find(".",first_dot+1)
            if second_dot < 0:
                return None
            try:
                version_tuple=(int(version_string[:first_dot]),int(version_string[first_dot+1:second_dot]), int(version_string[second_dot+1:]))
            except:
                return None
            if version_tuple[0] < 0 or version_tuple[1] < 0 or version_tuple[2] < 0:
                return None
            return version_tuple
    
        this_version_values = parse_version_string(cls.VERSION)
        other_version_values = parse_version_string(other_version)
        if this_version_values is None or other_version_values is None: 
            return None
        difference = None
        for i in range(len(this_version_values)):
            if this_version_values[i] != other_version_values[i]:
                difference = other_version_values[i] - this_version_values[i]
                return difference
        return difference
    
    @classmethod
    def clear_caches(cls):
        if "PARSED_FIELDS" in vars(cls).keys():
            delattr(cls, "PARSED_FIELDS")
        if "PARSED_SCHEMA" in vars(cls).keys():
            delattr(cls, "PARSED_SCHEMA")

    def indexer(self, keys):
        result_keys = set()
        if keys[0] == "functions":
            action_lists = [self.get_callbacks(), self.get_close_callbacks()]
            if self.graph_start is not None:
                for event_type, settings in self.graph_start.items():
                    if settings is None:
                        continue
                    if "setup" in settings:
                        action_lists.append(settings["setup"])
                    if "filters" in settings:
                        action_lists.append(settings["filters"])
            for event_type, settings in self.events.items():
                if "filters" in settings:
                    action_lists.append(settings["filters"])
                if "actions" in settings:
                    action_lists.append(settings["actions"])
                if "transitions" in settings:
                    for transition_num, transition_settings in enumerate(settings["transitions"]):
                        if "transition_filters" in transition_settings:
                            action_lists.append(transition_settings["transition_filters"])
                        if "transition_actions" in transition_settings:
                            action_lists.append(transition_settings["transition_actions"])

            for action_list in action_lists:
                for action in action_list:
                    if isinstance(action, dict):
                        for func_name in action.keys():
                            # probably would only have one key which is function name in each action
                            result_keys.add(func_name)
                    else:
                        result_keys.add(action)
            return [], list(result_keys)
        if keys[0] == "next_nodes":
            for event_type, settings in self.events.items():
                if "transitions" in settings:
                    for transition_num, transition_settings in enumerate(settings["transitions"]):
                        if type(transition_settings["node_names"]) is str:
                            result_keys.add(transition_settings["node_names"])
                        else:
                            for next_node in transition_settings["node_names"]:
                                result_keys.add(next_node)
            return [], list(result_keys)
        return None

class BaseNode:
    def __init__(self, graph_node:BaseGraphNode, session:typing.Union[None, SessionData.SessionData]=None, timeout_duration:timedelta=None) -> None:
        self.graph_node = graph_node
        self.session = session
        self.status = ITEM_STATUS.INACTIVE

        self.set_TTL(timeout_duration=timeout_duration if timeout_duration is not None else timedelta(seconds=-1))

    def set_TTL(self, timeout_duration:timedelta):
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

    def time_left(self) -> timedelta:
        return self.timeout - datetime.utcnow()
        
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