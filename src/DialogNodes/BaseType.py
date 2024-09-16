#TODO: is adding values onto fields such as event filters feasible?
#TODO: double check if inherited from parent class's set and update methods should be used (probably, but further down pipeline problem)
from datetime import datetime, timedelta
import typing
import src.utils.SessionData as SessionData
import yaml
import copy
from src.utils.Enums import POSSIBLE_PURPOSES, ITEM_STATUS

import src.utils.Cache as Cache
import src.utils.ValidationUtils as ValidationUtils
import src.utils.DotNotator as DotNotator
import src.utils.SectionUtils as SectionUtils

class BaseGraphNode:
    VERSION = "3.8.0"
    # this specifies the class variables that this class will add onto inherited class
    # variables.
    ADDED_FIELDS='''
options:
  - name: id
  - name: graph_start
    default: {}
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

    def get_validation_info(self):
        unique_next_nodes = set()
        function_set_list = []
        if self.graph_start is not None:
            for event_type, settings in self.graph_start.items():
                if settings is None:
                    continue
                if "setup" in settings:
                    function_set_list.append(ValidationUtils.FunctionSectionInfo(settings["setup"], self.id, POSSIBLE_PURPOSES.ACTION, "graph start setup for event {et}".format(et=event_type), event_type))
                if "filters" in settings:
                    function_set_list.append(ValidationUtils.FunctionSectionInfo(settings["filters"], self.id, POSSIBLE_PURPOSES.FILTER, "graph start filters for event {et}".format(et=event_type), event_type))
        function_set_list.append(ValidationUtils.FunctionSectionInfo(self.actions, self.id, POSSIBLE_PURPOSES.ACTION, "node enter actions"))
        function_set_list.append(ValidationUtils.FunctionSectionInfo(self.close_actions, self.id, POSSIBLE_PURPOSES.ACTION, "node close actions"))
        for event_type, settings in self.events.items():
            if "filters" in settings:
                function_set_list.append(ValidationUtils.FunctionSectionInfo(settings["filters"], self.id, POSSIBLE_PURPOSES.FILTER, f"node {event_type} event filters", event_type))
            if "actions" in settings:
                function_set_list.append(ValidationUtils.FunctionSectionInfo(settings["actions"], self.id, POSSIBLE_PURPOSES.ACTION, f"node {event_type} event actions", event_type))
            if "transitions" in settings:
                for transition_num, transition_settings in enumerate(settings["transitions"]):
                    next_nodes_count = BaseGraphNode.parse_node_names(transition_settings["node_names"])
                    for next_node in next_nodes_count:
                        unique_next_nodes.add(next_node)
                    if "tansition_counters" in transition_settings:
                        function_set_list.append(ValidationUtils.FunctionSectionInfo(transition_settings["transition_counters"],  self.id, POSSIBLE_PURPOSES.TRANSITION_COUNTER, f"node {event_type} event index {transition_num} transition counters", event_type))
                    if "transition_filters" in transition_settings:
                        function_set_list.append(ValidationUtils.FunctionSectionInfo(transition_settings["transition_filters"],  self.id, POSSIBLE_PURPOSES.TRANSITION_FILTER, f"node {event_type} event index {transition_num} transition filters", event_type))
                    if "transition_actions" in transition_settings:
                        function_set_list.append(ValidationUtils.FunctionSectionInfo(transition_settings["transition_actions"], self.id, POSSIBLE_PURPOSES.TRANSITION_ACTION, f"node {event_type} event index {transition_num} transition actions", event_type))
        return unique_next_nodes, function_set_list

    def __init__(self, options:dict) -> None:
        '''Instances hold specific settings for one graph node.

        Init Parameters
        ---
        * options - `dict`
            All options defined in the GraphNode class will be added as dot notation referencable fields on each GraphNode object.
            this parameter is a ditionary option name to values for the fields of this object.
            Makes sure all and only all fields listed in Graph node type's class are defined. values that are not primitives should be copied before passing in.
            On missing values, tries to use defaults from class.ADDED_FIELDS, otherwise raises an exception. Ignores extras.
        '''
        # need to get data for all fields that need to exist for node, so get list of all fields and their defaults and go through
        # passed in list for this instance's values
        # keeping track of missing fields
        self.normalize_input(options, insert_defaults=True)
        options_missing = []
        for field in self.__class__.get_node_fields():
            field_name = field["name"]
            if field_name in options:
                setattr(self, field_name, options[field_name])
            elif "default" in field:
                setattr(self, field_name, copy.deepcopy(field["default"]))
            else:
                options_missing.append(field_name)

        if "version" in options:
            setattr(self, "yaml_version", options["version"])
        else:
            setattr(self, "yaml_version", self.VERSION)

        # assuming all options found from getting node fields are required, so no default and nothing specified in passed in definition means fail
        if len(options_missing) > 0:
            raise Exception(f"node object of type {self.__class__.__name__} missing values for fields during init: {options_missing}")

        self.set_TTL(timeout_duration=timedelta(seconds=-1))

    @classmethod
    def normalize_input(cls, data, insert_defaults=True):
        '''takes already validated data and gets it ready for making a node with. this formats data to be consistent and inserts any default values
        if they are missing at top level if insert_defaults parameter is true. Any default values for nested structures are added as needed
        regardless of flag'''

        # get default values for top level of config
        # nested sections also have default values and formatting, not reflected in this
        base_fields = cls.get_node_fields()
        base_fields = {field["name"]: field for field in base_fields}

        if "version" not in data and insert_defaults:
            # if not named assuming version is for this.
            # should already be validated again this version so ok to try using this version
            data["version"] = cls.VERSION
        if "actions" not in data and insert_defaults:
            # pad actions with default empty indicator from base ones. reduce later checks by removing the "is key there check"
            data["actions"] = base_fields["actions"]["default"]
        else:
            SectionUtils.formatSection(data.get("actions", []), POSSIBLE_PURPOSES.ACTION)
        if "close_actions" not in data and insert_defaults:
            data["close_actions"] = base_fields["close_actions"]["default"]
        else:
            SectionUtils.formatSection(data.get("close_actions", []), POSSIBLE_PURPOSES.ACTION)
        if "TTL" not in data and insert_defaults:
            data["TTL"] = base_fields["TTL"]["default"]
        if "graph_start" not in data:
            if insert_defaults:
                # graph_start was not specified by the input to create this graph node, populating with default
                data["graph_start"] = base_fields["graph_start"]["default"]
        elif data["graph_start"] is not None:
            for event in data["graph_start"].keys():
                event_data = data["graph_start"][event]
                if event_data is None:
                    # event expected to have certain bits of data to reduce checks needed
                    data["graph_start"][event] = {"filters": [], "setup": []}
                    continue
                if isinstance(event_data.get("session_chaining"), str):
                    event_data["session_chaining"] = {event_data["session_chaining"]: SessionData.SessionData.DEFAULT_TTL}
                for settings in [(POSSIBLE_PURPOSES.FILTER, "filters"), (POSSIBLE_PURPOSES.ACTION, "setup")]:
                    purpose = settings[0]
                    action_list = settings[1]
                    if action_list not in event_data:
                        event_data[action_list] = []
                    else:
                        SectionUtils.formatSection(event_data.get(action_list, []), purpose)
        if "events" not in data:
            if insert_defaults:
                data["events"] = base_fields["events"]["default"]
        elif data["events"] is not None:
            for event in data["events"].keys():
                event_data = data["events"][event]
                if event_data is None:
                    data["events"][event] = {"filters": [], "actions": [], "transitions": []}
                    continue
                if "schedule_close" in event_data and isinstance(event_data["schedule_close"], str):
                        event_data["schedule_close"] = [event_data["schedule_close"]]
                for settings in [(POSSIBLE_PURPOSES.FILTER, "filters"), (POSSIBLE_PURPOSES.ACTION, "actions")]:
                    purpose = settings[0]
                    action_list = settings[1]
                    if action_list not in event_data:
                        event_data[action_list] = []
                    else:
                        SectionUtils.formatSection(event_data.get(action_list, []), purpose)
                if "transitions" not in event_data:
                    event_data["transitions"] = []
                    # since last checked item in the event, can continue since the rest is just formatting if transitions is in event
                    continue
                for index in range(len(event_data.get("transitions", []))):
                    transition = event_data["transitions"][index]
                    # node names can be a list, and can have multiple copies of one node, so formatting everything to be like that
                    if isinstance(transition["node_names"], str):
                        transition["node_names"] = {transition["node_names"]:1}
                    elif not isinstance(transition["node_names"], dict):
                        result = {}
                        for node_settings in transition["node_names"]:
                            if isinstance(node_settings, str):
                                result[node_settings] = 1
                            else:
                                result.update(node_settings)
                    for settings in [(POSSIBLE_PURPOSES.TRANSITION_COUNTER, "transition_counters"),
                                     (POSSIBLE_PURPOSES.TRANSITION_FILTER, "transition_filters"),
                                     (POSSIBLE_PURPOSES.TRANSITION_ACTION, "transition_actions")]:
                        purpose = settings[0]
                        action_list = settings[1]
                        if action_list not in transition:
                            transition[action_list] = []
                        else:
                            SectionUtils.formatSection(transition.get(action_list, []), purpose)
                    if "schedule_close" in transition and isinstance(transition["schedule_close"], str):
                        transition["schedule_close"] = [transition["schedule_close"]]
                    if isinstance(transition.get("session_chaining"), str):
                        transition["session_chaining"] = {transition["session_chaining"]: None}

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

    def is_graph_start(self, event_type:str):
        '''checks whether or not event of type event_type is allowed to start at this node.
        Must have event's key listed within graph_start section to be allowed to start

        Returns
        ---
        `bool` - whether or not graph is allowed to start at this node'''
        return event_type in self.graph_start

    def graph_starts_with_session(self, event_type:str):
        '''checks if the given event type requires setting up a session when starting this node.

        Returns
        ---
        `bool` - whether or not node starts with a session'''
        # graph starts with session if has event and session chaining is set to start
        # even though session start is dict, it only is allowed to have one key
        return self.is_graph_start(event_type) and "start" in self.graph_start[event_type].get("session_chaining", {})

    def get_graph_start_session_TTL(self, event_type:str):
        '''starting graph at node can start with a sesion, get the timeout for the session.

        Returns
        ---
        `Optional[float] - the duration to keep session around or None if does not start with session. Note that -1 signifies
        keep forever.`
        '''
        if self.graph_starts_with_session(event_type):
            # internally node has formatted so graph start always has one key("start") and value is timeout
            # value is never None
            duration = float(self.graph_start[event_type]["session_chaining"]["start"])
            if duration < -1:
                duration = -1
            return duration
        return None

    def get_graph_start_setup(self, event_type:str):
        '''returns a copy of the list of function names needed for setup phase of starting graph at this node for the given event_type.

        Returns
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded.
        Startup actions are not required, so will return an empty list if none are listed'''
        if self.is_graph_start(event_type) and "setup" in self.graph_start[event_type]:
            return copy.deepcopy(self.graph_start[event_type]["setup"])
        else:
            return []

    def get_graph_start_filters(self, event_type:str):
        '''returns a copy of the list of function names needed for filtering if graph can start at this node for the given event_type.

        Returns
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded. Filters aren't required, and will return empty list if none are listed'''
        if self.is_graph_start(event_type) and "filters" in self.graph_start[event_type]:
            return copy.deepcopy(self.graph_start[event_type]["filters"])
        else:
            return []

    def get_node_actions(self):
        '''get copy of list of node actions for when node is entered

        Return
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded.'''
        if self.actions is None:
            return []
        return copy.deepcopy(self.actions)

    def get_event_types(self):
        '''get event types this node will be waiting for

        Returns
        ---
        `set[str]` - names of event types waiting for'''
        return self.events.keys()
    
    def get_events(self):
        '''get a copy of all events settings. all event types waiting for and all settings for handling

        Returns
        ---
        `dict[str, dict[str, Any]]` - mapping of event type name to settings for that type'''
        return copy.deepcopy(self.events)

    def get_event_handling(self, event_type:str):
        '''get a copy of settings for handling the given event type

        Return
        ---
        `Optional[dict[str, Any]]` - the settings for handling this event type or None if not found'''
        if event_type in self.events:
            return copy.deepcopy(self.events[event_type])
        return None

    def get_event_filters(self, event_type:str):
        '''get a copy of settings for filters for event type named by event_type

        Return
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded.'''
        if event_type in self.events and "filters" in self.events[event_type]:
            return copy.deepcopy(self.events[event_type]["filters"])
        else:
            return []

    def get_event_actions(self, event_type:str):
        '''get a copy of settings for actions for event type named by event_type

        Return
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded.'''
        if event_type in self.events and "actions" in self.events[event_type]:
            return copy.deepcopy(self.events[event_type]["actions"])
        else:
            return []

    def get_event_close_flags(self, event_type:str):
        '''get a copy of the close flags for event type named by event_type
        
        return
        ---
        list of flags for what items to close after handling event and transitions. Note system will merge this and 
        transition's close flag.'''
        if event_type in self.events and "schedule_close" in self.events[event_type]:
            return copy.deepcopy(self.events[event_type]["schedule_close"])
        return []
    
    def has_transitions(self, event_type):
        if event_type in self.events and "transitions" in self.events[event_type]:
            return True
        else:
            return False

    def get_transitions(self, event_type):
        '''get a copy of settings for handling transitions for event type named by event_type

        Return
        ---
        `list[dict[str, Any]]` - list of settings for transitions for this event type'''
        if event_type in self.events and "transitions" in self.events[event_type]:
            return copy.deepcopy(self.events[event_type]["transitions"])
        else:
            return []

    def get_node_close_actions(self):
        '''get copy of list of node actions for when node is entered

        Return
        ---
        `list[dict[str, Any]]` - list where key is function name and any parameters recorded in Graph Node is in the value.
        value is None if nothing was recorded.'''
        if self.close_actions is None:
            return []
        return copy.deepcopy(self.close_actions)

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
        if "CLASS_FIELDS" in vars(cls).keys() and cls.CLASS_FIELDS is not None:
            # if there's a previous result of parsed definition cached, use that
            return copy.deepcopy(cls.CLASS_FIELDS[1])

        # nothing cached, need to actually find definitions for this class
        # grab inherited fields first
        parent_classes = cls.__bases__
        final_definitions = {}
        # assumes anything system will use as nodes have to be of BaseGraphNode. aka no duck typing
        if len(parent_classes) > 0:
            # need to gather all schema details inherited from nodes
            for parent in reversed(parent_classes):
                parent_definitions = parent.get_node_fields() if hasattr(parent, "get_node_fields") else {}
                # convert the returned list into a dict that's being used for easy finding
                for single_field in parent_definitions:
                    final_definitions[single_field["name"]] = copy.deepcopy(single_field)

        # load self definitions on top
        self_modifications = yaml.safe_load(cls.ADDED_FIELDS)
        if self_modifications is None:
            # this class doesn't have any fields to add, only base type cannot be allowed to do this
            if cls.__name__ == BaseGraphNode.__name__:
                raise Exception("Base type fields definition is critically malformed. whole system canot be used.")
            cls.CLASS_FIELDS = (datetime.utcnow(), list(final_definitions.values()))
            return list(final_definitions.values())
        if not isinstance(self_modifications, dict) or "options" not in self_modifications or self_modifications["options"] is None:
            raise Exception(f"node type <{cls.TYPE}> has badly formed fields. Must be either empty or have a list of fields in yaml format")
        # this class does have fields to add
        for single_field in self_modifications["options"]:
            if "name" not in single_field:
                raise Exception(f"node type <{cls.TYPE}> has malformed option: An option in definition is missing a name")
            final_definitions[single_field["name"]] = single_field

        cls.CLASS_FIELDS = (datetime.utcnow(), list(final_definitions.values()))
        return list(final_definitions.values())

    @classmethod
    def get_node_schema(cls):
        #TODO: probably need something to merge schemas, this will treat the two as independent, and can't use child classes to override base schema
        if "PARSED_SCHEMA" in vars(cls).keys() and cls.PARSED_SCHEMA is not None:
            # if there's a previous result of parsed schema cached, use that
            return copy.deepcopy(cls.PARSED_SCHEMA[1])

        parent_classes = cls.__bases__
        final_schema = {"allOf": []}
        # assumes anything system will use as nodes have to be of BaseGraphNode. aka no duck typing
        if len(parent_classes) > 0:
            # need to gather all schema details inherited from nodes
            for parent in reversed(parent_classes):
                parent_definitions = parent.get_node_schema() if hasattr(parent, "get_node_schema") else {"allOf": []}
                for schema_fragment in parent_definitions["allOf"]:
                    final_schema["allOf"].append(schema_fragment)

        # load self schema on top
        self_schema = yaml.safe_load(cls.SCHEMA)
        if self_schema is None:
            # this class doesn't have any schema to add, only base type cannot be allowed to do this
            if cls.__name__ == BaseGraphNode.__name__:
                raise Exception("Base type schema is critically malformed. whole system canot be used.")
            cls.PARSED_SCHEMA = (datetime.utcnow(), final_schema)
            return copy.deepcopy(final_schema)
        if not isinstance(self_schema, dict):
            raise Exception(f"node type <{cls.TYPE}> seems to have badly formed schema.")
        final_schema["allOf"].append(self_schema)
        cls.PARSED_SCHEMA = (datetime.utcnow(), final_schema)
        return copy.deepcopy(final_schema)
    
    @classmethod
    def get_version(cls):
        '''get the loaded Graph Node class version'''
        return cls.VERSION

    @classmethod
    def check_version_compatibility(cls, other_version):
        '''Checks if the passed in version is compatiple with Node Definition. ie if the classes can handle data that was written for the other version
        
        Return
        ---
        `tuple[bool, str]` - first element is whether the version is compatible, the second is any error or warning messages to send.
        Message can say what is wrong and what could be updated'''
        # note keep this and the one in compare_versions in sync
        def parse_version_string(version_string):
            '''
            Return
            ---
            Optional[tuple]
            '''
            if not isinstance(version_string, str):
                return None
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
        None if could not compare the versions, which can be because one of the version strings is invalid or otherwise unknown.
        Otherwise returns the signed difference between the two versions. Positive means other_version is ahead.
        The difference is the most signification digit that has a difference. ie 3.2 compare_version(3.7) returns 5,
        5.3 compare_version(3.6) returns -2'''
        def parse_version_string(version_string):
            '''
            Return
            ---
            Optional[tuple]
            '''
            if not isinstance(version_string, str):
                return None
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
        difference = 0
        for i in range(len(this_version_values)):
            if this_version_values[i] != other_version_values[i]:
                difference = other_version_values[i] - this_version_values[i]
                return difference
        return difference

    @classmethod
    def clear_caches(cls):
        # TODO: if auto detection of stale cache is needed, timestamps were added
        if "CLASS_FIELDS" in vars(cls).keys():
            delattr(cls, "CLASS_FIELDS")
        if "PARSED_SCHEMA" in vars(cls).keys():
            delattr(cls, "PARSED_SCHEMA")

    def indexer(self, keys):
        '''custom override function for dot parser for the purpose of chainging how Graph Node is indexed. 
        Changes how functions are indexed by. Data structure has them split into different storage areas
        but want to index by each unique function'''
        def grab_from_subsection(subsection):
            result_function_names = set()
            for action in subsection:
                if isinstance(action, dict):
                    for func_name in action.keys():
                        # probably would only have one key which is function name in each action
                        result_function_names.add(func_name)
                elif issubclass(action.__class__, SectionUtils.SubSection):
                    if isinstance(action, SectionUtils.IfSubSection):
                        sub_section_results = grab_from_subsection(action.filters)
                        for name in sub_section_results: result_function_names.add(name)
                        sub_section_results = grab_from_subsection(action.actions)
                        for name in sub_section_results: result_function_names.add(name)
                    else:
                        sub_section_results = grab_from_subsection(action.callbacks)
                        for name in sub_section_results: result_function_names.add(name)
                else:
                    result_function_names.add(action)
            return result_function_names

        result_keys = set()
        if keys[0] == "functions":
            # when specifying index by functions do it for all functions used, aka all sections of functions
            # step 1 is gathering all sections
            action_lists = [self.get_node_actions(), self.get_node_close_actions()]
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
                        if "transition_counters" in transition_settings:
                            action_lists.append(transition_settings["transition_counters"])
                        if "transition_filters" in transition_settings:
                            action_lists.append(transition_settings["transition_filters"])
                        if "transition_actions" in transition_settings:
                            action_lists.append(transition_settings["transition_actions"])
            # after gathering all functions, parse for function name
            for action_list in action_lists:
                sub_section_results = grab_from_subsection(action_list)
                for name in sub_section_results: result_keys.add(name)
            return keys[1:], list(result_keys)
        # design for 3.8.0 onwards allows run-time changing next_nodes with transition_counters.
        # disabling this section because it only will be able to see what is recorded in yaml which might be 
        # wrong when transition counters are used and that might be incorrect
        # elif keys[0] == "next_nodes":
        #     for event_type, settings in self.events.items():
        #         if "transitions" in settings:
        #             for transition_num, transition_settings in enumerate(settings["transitions"]):
        #                 for next_node in transition_settings["node_names"]:
        #                     result_keys.add(next_node)
        #     return keys[1:], list(result_keys)
        else:
            # all other searched for things. just use the search itself. (skipping the custom oerride though, to prevent looping)
            return [], DotNotator.parse_dot_notation(keys, self, custom_func_name="indexer", skip_first_custom=True)

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
        if self.timeout is None:
            return None
        return self.timeout - datetime.utcnow()

    def activate(self):
        self.status = ITEM_STATUS.ACTIVE
        if self.session is not None:
            self.session.activate()

    def is_active(self):
        return self.status == ITEM_STATUS.ACTIVE

    def notify_closing(self):
        self.status = ITEM_STATUS.CLOSING

    def close(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.status = ITEM_STATUS.CLOSED