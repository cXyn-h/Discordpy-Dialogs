import src.utils.CallbackUtils as cbUtils
import src.utils.DotNotator as DotNotator
import src.DialogNodes.BaseType as BaseType
import random
import inspect
from datetime import datetime, timedelta
from src.utils.Enums import POSSIBLE_PURPOSES
from enum import Enum

class YAML_SELECTION(Enum):
    EVENT="event"
    SECTION="section"
    CONTROL="control"
    ACTIVE_NODE="active_node"
    ACTIVE_SESSION= "active_session"
    GOAL_NODE= "goal_node"
    GOAL_SESSION="goal_session"

REGEX_OR_INPUT_SOURCES = "|".join([choice.value for choice in YAML_SELECTION])
REGEX_OR_OUTPUT_SOURCES = "|".join([choice.value for choice in YAML_SELECTION if choice not in [YAML_SELECTION.EVENT]])
NODES_AND_SESSION = [YAML_SELECTION.ACTIVE_NODE, YAML_SELECTION.ACTIVE_SESSION, YAML_SELECTION.GOAL_NODE, YAML_SELECTION.GOAL_SESSION]
NODES = [YAML_SELECTION.ACTIVE_NODE, YAML_SELECTION.GOAL_NODE]
SESSIONS = [YAML_SELECTION.ACTIVE_SESSION, YAML_SELECTION.GOAL_SESSION]

def select_from_pack(name, datapack):
    '''uses the vlues of YAML_SELECTION to decide which node, session, section data etc from the datapack to return.
    
    Return
    ----
    None if specified location is not defined, otherwise the place to store data in the object or in case of event, the event object itself'''
    location = None
    if name.startswith(YAML_SELECTION.EVENT.value):
        location = datapack.event
    elif name.startswith(YAML_SELECTION.SECTION.value):
        location = datapack.section_data
    elif name.startswith(YAML_SELECTION.ACTIVE_NODE.value):
        location = datapack.active_node
    elif name.startswith(YAML_SELECTION.ACTIVE_SESSION.value) and datapack.active_node.session is not None:
        location = datapack.active_node.session.data
    elif name.startswith(YAML_SELECTION.GOAL_NODE.value):
        location = datapack.goal_node
    elif name.startswith(YAML_SELECTION.GOAL_SESSION.value) and datapack.goal_node is not None and datapack.goal_node.session is not None:
        location = datapack.goal_node.session.data
    elif name.startswith(YAML_SELECTION.CONTROL.value):
        location = datapack.control_data
    return location

def handle_save_data(save_data, save_locations, datapack):
    for save_location in save_locations:
        location = select_from_pack(save_location, datapack)
        if location is None:
            continue
        
        split_names = save_location.split(".")
        location = DotNotator.parse_dot_notation(split_names[1:-1], location, None)
        
        field_name = split_names[-1]
        if issubclass(location.__class__, BaseType.BaseNode):
            setattr(location, field_name, save_data)
        elif isinstance(location, dict):
            location[field_name] = save_data

def merge_overrides(base, override):
    result = base
    if isinstance(base, dict):
        result.update(override)
    elif isinstance(base, list):
        result.extend(override)
    else:
        result = override
    return result

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="optional", schema={"type":"object", "properties":{
    "grab_location": {
        "type": "string",
        "description": "what to grab from event",
        "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
    },
    "save_locations": {
        "type": "array",
        "items": {
            "type": "string",
            "description": "where to save grabbed data",
            "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"
        }
    },
    "delete_after": {
        "type": "boolean"
    }
}})
def transfer_data(data:cbUtils.CallbackDatapack):
    func_override_key = "transfer_data_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    section_parameter = merge_overrides(data.base_parameter, section_overrides)
    grab_location_name = section_parameter["grab_location"]
    save_locations = section_parameter["save_locations"]

    if grab_location_name is None or save_locations is None:
        return
    
    grab_location = select_from_pack(grab_location_name, data)
    if grab_location is None:
        return
    split_grab = grab_location_name.split(".")
    grab_location = DotNotator.parse_dot_notation(split_grab[1:-1], grab_location, None)
    save_data = DotNotator.parse_dot_notation(split_grab[-1:], grab_location, None)

    handle_save_data(save_data, save_locations, data)

    if "delete_after" in section_parameter and section_parameter["delete_after"]:
        if issubclass(grab_location.__class__, BaseType.BaseNode):
            delattr(grab_location, split_grab[-1], save_data)
        elif isinstance(grab_location, dict):
            del grab_location[split_grab[-1]]

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={
"type": "object", "properties": {
    "value": {},
    "save_locations": {
        "type": "array",
        "items": {
            "type": "string",
            "description": "where to save grabbed data",
            "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"
        }
    }
}})
def save_data(data:cbUtils.CallbackDatapack):
    func_override_key = "save_data_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    section_parameter = merge_overrides(data.base_parameter, section_overrides)
    save_locations = section_parameter["save_locations"]
    saved_value = section_parameter["value"]

    if save_locations is None:
        return
    
    handle_save_data(saved_value, save_locations, data)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={
"type":"object", "properties":{
    "location": {
        "type": "string",
        "description": "where to save grabbed data",
        "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"
    },
    "increment": {"type": "number"},
}})
def increment_value(data:cbUtils.CallbackDatapack):
    func_override_key = "increment_value_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    section_parameter = merge_overrides(data.base_parameter, section_overrides)
    location = section_parameter["location"]
    increment = section_parameter["increment"]
    split_names = location.split(".")
    
    location = select_from_pack(location, data)
    if location is None:
        return
    location = DotNotator.parse_dot_notation(split_names[1:-1], location, None)
    
    field_name = split_names[-1]
    if issubclass(location.__class__, BaseType.BaseNode):
        setattr(location, field_name, getattr(location, field_name) + increment)
    elif isinstance(location, dict):
        location[field_name] = location[field_name] + increment

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], has_parameter="always", schema={"type":"number"})
def random_chance(data:cbUtils.CallbackDatapack):
    func_override_key = "random_chance_override"
    section_overrides = data.section_data.get(func_override_key, None)
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    bar = data.base_parameter if data.base_parameter is not None else (section_overrides if section_overrides is not None else 1)

    num = random.random()
    return num < bar

#TODO: do nested support
    # "variable": {"type":"string", "pattern": "^(current_session|goal_session|current_node|goal_node|node|session)(\.[\w]+)+$"},
@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], has_parameter="always", schema={"type":"object", "properties":{
    "variable": {"type":"string", "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"},
    "operator": {"type": "string", "enum":["==", "<", ">", "<=", ">=", "!="]},
    "value": {"type": "integer"}
}, "required": ["operator", "variable", "value"]})
def simple_compare(data:cbUtils.CallbackDatapack):
    func_override_key = "simple_compare_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]

    active_node:BaseType.BaseNode = data.active_node
    goal_node = data.goal_node
    settings = merge_overrides(data.base_parameter, section_overrides)

    variable_value = None
    split_names = settings["variable"].split(".")
    location = select_from_pack(settings["variable"], data)
    if location is None:
        return
    variable_value = DotNotator.parse_dot_notation_string(split_names[1:], location, None)
    
    if variable_value is None:
        return False

    benchmark = settings["value"]
    if settings["operator"] == "==":
        return variable_value == benchmark
    elif settings["operator"] == "<":
        return variable_value < benchmark
    elif settings["operator"] == ">":
        return variable_value > benchmark
    elif settings["operator"] == "<=":
        return variable_value <= benchmark
    elif settings["operator"] == ">=":
        return variable_value >= benchmark
    elif settings["operator"] == "!=":
        return variable_value != benchmark
    
@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "objects": {"onfOf":[
        {"type":"string", "enum":[choice.value for choice in NODES_AND_SESSION]},
        {"type":"array", "items":{"type":"string","enum":[choice.value for choice in NODES_AND_SESSION]}}]},
    "seconds": {"type": "number"}
}, "required":["objects"]})
def update_timeout(data:cbUtils.CallbackDatapack):
    """updates the values of timeout to number of seconds in the future for the nodes or sessions listed. If `seconds` isn't specified, defaults to 3 and 10 minutes
    for nodes and sessions respectively"""
    func_override_key = "update_timeout_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]

    active_node:BaseType.BaseNode = data.active_node
    goal_node:BaseType.BaseNode = data.goal_node
    settings = data.base_parameter
    if "objects" in section_overrides:
        settings["objects"] = section_overrides["objects"]
    if "seconds" in section_overrides:
        settings["seconds"] = section_overrides["seconds"]

    targets = settings["objects"]
    if isinstance(targets, str):
        targets = [targets]

    if YAML_SELECTION.ACTIVE_NODE.value in targets:
        time = timedelta(seconds=180)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        active_node.set_TTL(time)
    if YAML_SELECTION.ACTIVE_SESSION.value in targets and active_node.session is not None:
        time = timedelta(seconds=600)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        active_node.session.set_TTL(time)
    if YAML_SELECTION.GOAL_NODE.value in targets and goal_node is not None:
        time = timedelta(seconds=180)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        goal_node.set_TTL(time)
    if YAML_SELECTION.GOAL_SESSION.value in targets and goal_node is not None and goal_node.session is not None:
        time = timedelta(seconds=600)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        goal_node.session.set_TTL(time)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "grab_location": {
        "type": "string",
        "description": "what to grab from event",
        "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
    },
    "save_locations": {
        "type": "array",
        "items": {
            "type": "string",
            "description": "where to save grabbed data",
            "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"
        }
    }
}})
async def call_on_object(data:cbUtils.CallbackDatapack):
    func_override_key = "call_on_object_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    section_parameter = merge_overrides(data.base_parameter, section_overrides)
    grab_location_name = section_parameter["grab_location"]
    save_locations = section_parameter("save_locations")

    if grab_location_name is None or save_locations is None:
        return

    grab_location = select_from_pack(grab_location_name, data)
    if grab_location is None:
        return
    split_grab = grab_location_name.split(".")
    grab_location = DotNotator.parse_dot_notation_string(split_grab[1:], grab_location, None)
    if inspect.isawaitable(grab_location):
        save_data = await grab_location()
    save_data = grab_location()

    handle_save_data(save_data, save_locations, data)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "location": {
        "type": "string",
        "description": "what to grab from event",
        "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
    }
}})
def delete_data(data:cbUtils.CallbackDatapack):
    func_override_key = "delete_data_override"
    section_overrides = data.section_data.get(func_override_key, {})
    if func_override_key in data.section_data:
        del data.section_data[func_override_key]
    section_parameter = merge_overrides(data.base_parameter, section_overrides)
    grab_location_name = section_parameter["location"]

    if grab_location_name is None:
        return
    
    grab_location = select_from_pack(grab_location_name, data)
    if grab_location is None:
        return
    split_grab = grab_location_name.split(".")
    grab_location = DotNotator.parse_dot_notation_string(split_grab[1:-1], grab_location, None)
    save_data = DotNotator.parse_dot_notation_string(split_grab[-1], grab_location, None)

    if issubclass(grab_location.__class__, BaseType.BaseNode):
        delattr(grab_location, split_grab[-1], save_data)
    elif isinstance(grab_location, dict):
        del grab_location[split_grab[-1]]

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], has_parameter="always", schema={
    "type": "string",
    "description": "what to grab from event",
    "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
})
def has_data(data:cbUtils.CallbackDatapack):
    func_override_key = "has_data_override"
    location_name = data.base_parameter
    if func_override_key in data.section_data:
        location_name = data.section_data[func_override_key]
        del data.section_data[func_override_key]

    if location_name is None:
        return
    
    obj = select_from_pack(location_name, data)
    if obj is None:
        return
    split_grab = location_name.split(".")
    obj = DotNotator.parse_dot_notation_string(split_grab[1:-1], obj, None)

    if obj:
        if issubclass(obj.__class__, BaseType.BaseNode):
            return split_grab[-1] in vars(obj)
        elif isinstance(obj, dict):
            return split_grab[-1] in obj
    return False


@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def always_false_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def always_true_filter(data:cbUtils.CallbackDatapack):
    return True

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION])
def debugging_action(data:cbUtils.CallbackDatapack):
    print(f"DEBUGGING ACTION!! For node <{id(data.active_node)}><{data.active_node.graph_node.id}> event <{id(data.event)}><{type(data.event)}>")

dialog_func_info = {transfer_data:{}, always_false_filter:{}, always_true_filter:{}, debugging_action:{},
                    save_data:{}, random_chance:{}, simple_compare:{}, increment_value:{}, update_timeout:{},
                    call_on_object:{}, delete_data:{}, has_data:{}}

