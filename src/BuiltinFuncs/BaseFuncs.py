import random
import inspect
import typing
from datetime import datetime, timedelta
from copy import copy, deepcopy
from enum import Enum
from jsonschema import validate, ValidationError

from src.utils.SessionData import SessionData
import src.utils.CallbackUtils as cbUtils
import src.utils.DotNotator as DotNotator
from src.utils.Enums import POSSIBLE_PURPOSES

import src.DialogNodes.BaseType as BaseType

class YAML_SELECTION(Enum):
    '''enum for all possible location selections for reading or storing data for callbacks'''
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
    '''uses the values of YAML_SELECTION to decide which node, session, section data etc from the datapack to return.
    
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
        location = datapack.active_node.session
    elif name.startswith(YAML_SELECTION.GOAL_NODE.value):
        location = datapack.goal_node
    elif name.startswith(YAML_SELECTION.GOAL_SESSION.value) and datapack.goal_node is not None and datapack.goal_node.session is not None:
        location = datapack.goal_node.session
    elif name.startswith(YAML_SELECTION.CONTROL.value):
        location = datapack.control_data
    return location

def handle_save_data(save_data, save_locations, datapack):
    '''default way to find where to save and save data. can take multiple locations in and saves deepcopies of the data'''
    for save_location in save_locations:
        loop_save_data = deepcopy(save_data)
        handle_save_ref(loop_save_data, save_location, datapack)

def handle_save_ref(save_data, save_location, datapack):
    '''special case of saving but no copying data. not recommended to do this in multiple locations'''
    split_names = save_location.split(".")
    location:"typing.Union[BaseType.BaseNode, SessionData]" = select_from_pack(save_location, datapack)

    if location is None:
        # didn't specify a valid location of datapack. can't save
        return

    if split_names[0] in [loc.value for loc in NODES_AND_SESSION]:
        # nodes and sessions handle saving themselves, so just pase location and data to them
        location.set_data(split_names[1:], save_data)
    else:
        location = DotNotator.parse_dot_notation(split_names[1:-1], location, None, custom_func_name="get_data")
    
        field_name = split_names[-1]
        if isinstance(location, dict):
            location[field_name] = save_data
        elif isinstance(location, list):
            location.append(save_data)
        elif issubclass(location.__class__, BaseType.BaseNode) or isinstance(location, SessionData):
            location.set_data([field_name], save_data)
        else:
            setattr(location, field_name, save_data)

def handle_delete_data(data_location, datapack):
    split_names = data_location.split(".")
    location:"typing.Union[BaseType.BaseNode, SessionData]" = select_from_pack(data_location, datapack)

    if location is None:
        return

    if split_names[0] in [loc.value for loc in NODES_AND_SESSION]:
        # nodes and sessions handle saving themselves, so just pase location and data to them
        location.delete_data(split_names[1:])
    else:
        location = DotNotator.parse_dot_notation(split_names[1:-1], location, None, custom_func_name="get_data")
    
        field_name = split_names[-1]
        if isinstance(location, dict):
            del location[field_name]
        elif isinstance(location, list):
            location.pop(field_name)
        elif issubclass(location.__class__, BaseType.BaseNode) or isinstance(location, SessionData):
            location.delete_data([field_name])
        else:
            delattr(location, field_name)

def default_runtime_input_finder(runtime_input_key, datapack:cbUtils.CallbackDatapack, default=None):
    '''default way of fetching runtime overrides of parameters. Expects that data to be in section data and returns it after removing from section data'''
    if runtime_input_key in datapack.section_data:
        section_overrides = datapack.section_data.get(runtime_input_key, None)
        del datapack.section_data[runtime_input_key]
        return section_overrides
    return default

def default_merge_settings(base, override):
    '''default strategy of merging parameter settings for callbacks. If paramter is dictionary, then if override is a dict, updates base with override
    (if it is a nested dictionary, will only call update with top level keys, nested objects are replaced); 
    if list, then if override is also a list, appends all elements; otherwise only sets value if override is not None'''
    result = base
    if isinstance(base, dict):
        if isinstance(override, dict):
            result.update(override)
    elif isinstance(base, list):
        if isinstance(override, list):
            result.extend(override)
    elif override is not None:
        result = override
    return result

def default_handle_run_input(runtime_input_key, data:cbUtils.CallbackDatapack, merge_handler=default_merge_settings):
    '''default way of accepting runtime input. searches for input in section_data only and removes data from section_data after use. Uses passed function to merge two sets of settings'''
    section_overrides = default_runtime_input_finder(runtime_input_key, data)
    return merge_handler(data.base_parameter, section_overrides)

def get_data(datapack, location:'str, l', default=None):
    '''use dot separate location name and grab whatever is stored there or return default if not found'''
    grab_location = select_from_pack(location, datapack)
    if grab_location is None:
        return default
    if isinstance(location, str):
        split_grab = location.split(".")
    else:
        split_grab = location
    return DotNotator.parse_dot_notation(split_grab[1:], grab_location, default, custom_func_name="get_data")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="transfer_data_override", schema={"type":"object", "properties":{
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
}}, description_blurb="moves data between storage(s) and workspace areas")
def transfer_data(data:cbUtils.CallbackDatapack):
    section_parameter = default_handle_run_input("transfer_data_override", data)
    grab_location_name = section_parameter["grab_location"]
    save_locations = section_parameter["save_locations"]

    if grab_location_name is None or save_locations is None:
        return
    
    save_data = get_data(data, grab_location_name)

    handle_save_data(save_data, save_locations, data)

    if "delete_after" in section_parameter and section_parameter["delete_after"]:
        handle_delete_data(grab_location_name, data)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="save_data_override", schema={
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
}}, description_blurb="puts value in storage location(s)")
def save_data(data:cbUtils.CallbackDatapack):
    section_parameter = default_handle_run_input("save_data_override", data)
    save_locations = section_parameter["save_locations"]
    saved_value = section_parameter["value"]

    if save_locations is None:
        return
    
    handle_save_data(saved_value, save_locations, data)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="increment_value_override", schema={
"type":"object", "properties":{
    "location": {
        "type": "string",
        "description": "where to save grabbed data",
        "pattern": REGEX_OR_OUTPUT_SOURCES+"(\.[\w\d]*)+"
    },
    "increment": {"type": "number"},
}},
description_blurb="adds on increment to number saved in given location")
def increment_value(data:cbUtils.CallbackDatapack):
    section_parameter = default_handle_run_input("increment_value_override", data)
    location = section_parameter["location"]
    increment = section_parameter["increment"]

    old_value = get_data(data, location)

    handle_save_data(old_value + increment, [location], data)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], runtime_input_key="random_chance_override", schema={"type":"number", "maximum": 1, "minimun": 0},
                           description_blurb="RNG with customizable chance (as a decimal number)")
def random_chance(data:cbUtils.CallbackDatapack):
    bar = default_handle_run_input("random_chance_override", data)
    if bar is None:
        bar = 1

    num = random.random()
    return num < bar

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], runtime_input_key="random_choice_override", schema={
    "type": "object",
    "properties": {
        "choices": {
            "type": "array"
        },
        "save_location": {
            "type": "string"
        }
    }
},
                           description_blurb="RNG with customizable chance (as a decimal number)")
def random_choice(data:cbUtils.CallbackDatapack):
    settings = default_handle_run_input("random_choice_override", data)
    chosen_ind = random.randint(0, len(settings["choices"])-1)
    chosen = settings["choices"][chosen_ind]

    handle_save_data(chosen, [settings["save_location"]], data)

#TODO: do nested support
    # "variable": {"type":"string", "pattern": "^(current_session|goal_session|current_node|goal_node|node|session)(\.[\w]+)+$"},
@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], runtime_input_key="simple_compare_override", schema={"type":"object", "properties":{
    "variable": {"type":"string", "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"},
    "operator": {"type": "string", "enum":["==", "<", ">", "<=", ">=", "!="]},
    "value": {"type": "integer"}
}, "required": ["operator", "variable", "value"]}, description_blurb="string for comparing variable, to single value")
def simple_compare(data:cbUtils.CallbackDatapack):
    settings = default_handle_run_input("simple_compare_override", data)

    variable_value = get_data(data, settings["variable"], default=None)
    print(f"debugging {variable_value}")
    
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
    
@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="update_timeout_override", schema={"type":"object", "properties":{
    "objects": {"onfOf":[
        {"type":"string", "enum":[choice.value for choice in NODES_AND_SESSION]},
        {"type":"array", "items":{"type":"string","enum":[choice.value for choice in NODES_AND_SESSION]}}]},
    "seconds": {"type": "number"}
}, "required":["objects"]}, description_blurb="updates timeout to be provided seconds from now")
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

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="call_on_object_override", schema={"type":"object", "properties":{
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
}}, description_blurb="calls function at grab_location and stores result value")
async def call_on_object(data:cbUtils.CallbackDatapack):
    section_parameter = default_handle_run_input("call_on_object_override", data)
    grab_location_name = section_parameter["grab_location"]
    save_locations = section_parameter["save_locations"]

    if grab_location_name is None or save_locations is None:
        return

    func = get_data(data, grab_location_name)
    if func is None:
        return
    if inspect.isawaitable(func):
        save_data = await func()
    elif callable(func) :
        save_data = func()
    else:
        return

    handle_save_data(save_data, save_locations, data)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="delete_data_override", schema={"type":"object", "properties":{
    "location": {
        "type": "string",
        "description": "what to grab from event",
        "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
    }
}}, description_blurb="delets value at location")
def delete_data(data:cbUtils.CallbackDatapack):
    section_parameter = default_handle_run_input("delete_data_override", data)
    grab_location_name = section_parameter["location"]

    if grab_location_name is None:
        return
    
    handle_delete_data(grab_location_name, data)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], runtime_input_key="has_data_override", schema={
    "type": "string",
    "description": "what to grab from event",
    "pattern": REGEX_OR_INPUT_SOURCES+"(\.[\w\d]*)+"
}, description_blurb="checks if given location exists")
def has_data(data:cbUtils.CallbackDatapack):
    location_name = default_handle_run_input("has_data_override", data)

    if location_name is None:
        return
    
    obj = select_from_pack(location_name, data)
    if obj is None:
        return False

    obj = get_data(data, location_name, None)
    return obj is None

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def did_session_timeout(data:cbUtils.CallbackDatapack):
    return isinstance(data.event, dict) and "type" in data.event and data.event["type"] == "Session"

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def did_node_timeout(data:cbUtils.CallbackDatapack):
    return isinstance(data.event, dict) and "type" in data.event and data.event["type"] == "Node"

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], description_blurb="always says False")
def always_false_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], description_blurb="always says True")
def always_true_filter(data:cbUtils.CallbackDatapack):
    return True

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], description_blurb="custom callback way to say close", schema={
    "type": "object",
    "properties": {
        "close_node": {
            "type": "boolean"
        },
        "close_session": {
            "type": "boolean"
        }
    }
})
def schedule_close(data:cbUtils.CallbackDatapack):
    settings = data.base_parameter
    if "close_node" in settings:
        data.control_data["close_node"] = settings["close_node"]
    if "close_session" in settings:
        data.control_data["close_session"] = settings["close_session"]

dialog_func_info = {transfer_data:{}, always_false_filter:{}, always_true_filter:{},
                    save_data:{}, random_chance:{}, random_choice:{}, simple_compare:{}, increment_value:{}, update_timeout:{},
                    call_on_object:{}, delete_data:{}, has_data:{}, did_session_timeout:{}, schedule_close:{}}

