import src.utils.callbackUtils as cbUtils
import src.DialogNodes.BaseType as BaseType
import random
from datetime import datetime, timedelta
from src.utils.Enums import POSSIBLE_PURPOSES

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "key": {"type": "string"}
}, "required":["key"]})
def save_event_data(data:cbUtils.CallbackDatapack):

    if hasattr(data.event, data.parameter["key"]):
        data.parameter["value"] = getattr(data.event, data.parameter["key"])
        save_data(data)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={
"type": "object", "properties": {
    "key": {"type":"string"},
    "value": {},
    "locations": {"onfOf":[{"type":"string","enum":["session","node"]},{"type":"array", "items":{"type":"string","enum":["session","node"]}}]}
}, "required": ["key", "value"]})
def save_data(data:cbUtils.CallbackDatapack):
    locations = data.parameter["locations"] if "locations" in data.parameter else "node"
    node = data.goal_node
    if data.goal_node is None:
        node = data.active_node

    print(f"saving data, key <{data.parameter['key']}>, value <{data.parameter['value']}> locations <{data.parameter['locations']}>")
    if (locations == "session" or "session" in locations) and node.session is not None:
        node.session.data[data.parameter["key"]] = data.parameter["value"]
        print(f"after saving to session, data is now <{node.session.data}>")
    if (locations == "node" or "node" in locations):
        setattr(node, data.parameter["key"], data.parameter["value"])
        print(f"after saving to node, node has property value: <{getattr(node, data.parameter['key'])}>")

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={
"type":"object", "properties":{
    "key": {"type": "string"},
    "value":{},
    "location":{"type":"string","enum":["session","node"]}
}, "required":["key", "value", "location"]})
def increment_value(data:cbUtils.CallbackDatapack):
    location = data.parameter["location"]
    node:BaseType.BaseNode = data.goal_node
    if data.goal_node is None:
        node = data.active_node

    if location == "session" and node.session is not None:
        node.session.data[data.parameter["key"]] += data.parameter["value"]
    elif location == "node":
        existing_value = getattr(node, data.parameter["key"])
        setattr(node, data.parameter["key"], existing_value+data.parameter["value"])

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER], has_parameter="always", schema={"type":"number"})
def random_chance(data:cbUtils.CallbackDatapack):
    num = random.random()
    return num < data.parameter

#TODO: do nested support
    # "variable": {"type":"string", "pattern": "^(current_session|goal_session|current_node|goal_node|node|session)(\.[\w]+)+$"},
@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], has_parameter="always", schema={"type":"object", "properties":{
    "variable": {"type":"string", "pattern": "^(node|session).[\w]+$"},
    "operator": {"type": "string", "enum":["==", "<", ">", "<=", ">=", "!="]},
    "value": {"type": "integer"}
}, "required": ["operator", "variable", "value"]})
def simple_compare(data:cbUtils.CallbackDatapack):
    active_node:BaseType.BaseNode = data.active_node
    goal_node = data.goal_node
    settings = data.parameter

    if goal_node is None:
        node = active_node
    else:
        node = goal_node

    variable_value = None
    split_names = settings["variable"].split(".")
    if split_names[0] == "node" and hasattr(node, split_names[1]):
        variable_value = getattr(node, split_names[1])
    elif node.session is not None:
        variable_value = node.session[split_names[1]]
    
    if variable_value is None:
        return False

    value2 = data.parameter["value"]
    if settings["operator"] == "==":
        return variable_value == value2
    elif settings["operator"] == "<":
        return variable_value < value2
    elif settings["operator"] == ">":
        return variable_value > value2
    elif settings["operator"] == "<=":
        return variable_value <= value2
    elif settings["operator"] == ">=":
        return variable_value >= value2
    elif settings["operator"] == "!=":
        return variable_value != value2
    
@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "objects": {"onfOf":[
        {"type":"string", "enum":["current_session","goal_session","current_node","goal_node"]},
        {"type":"array", "items":{"type":"string","enum":["current_session","goal_session","current_node","goal_node"]}}]},
    "seconds": {"type": "number"}
}, "required":["objects"]})
def update_timeout(data:cbUtils.CallbackDatapack):
    """updates the values of timeout to number of seconds in the future for the nodes or sessions listed. If `seconds` isn't specified, defaults to 3 and 10 minutes
    for nodes and sessions respectively"""
    active_node:BaseType.BaseNode = data.active_node
    goal_node:BaseType.BaseNode = data.goal_node
    settings = data.parameter

    targets = settings["objects"]
    if isinstance(targets, str):
        targets = [targets]

    if "current_node" in targets:
        time = timedelta(seconds=180)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        active_node.set_TTL(time)
    if "current_sesion" in targets and active_node.session is not None:
        time = timedelta(seconds=600)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        active_node.session.set_TTL(time)
    if "goal_node" in targets and goal_node is not None:
        time = timedelta(seconds=180)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        goal_node.set_TTL(time)
    if "goal_sesion" in targets and goal_node is not None and goal_node.session is not None:
        time = timedelta(seconds=600)
        if "seconds" in settings:
            time = timedelta(seconds=settings["seconds"])
        goal_node.session.set_TTL(time)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def debugging_false_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def debugging_true_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION])
def debugging_action(data:cbUtils.CallbackDatapack):
    print(f"DEBUGGING ACTION!! For node <{id(data.active_node)}><{data.active_node.graph_node.id}> event <{id(data.event)}><{type(data.event)}>")

dialog_func_info = {save_event_data:{}, debugging_false_filter:{}, debugging_true_filter:{}, debugging_action:{}, save_data:{}, random_chance:{}, simple_compare:{}, increment_value:{}, update_timeout:{}}

