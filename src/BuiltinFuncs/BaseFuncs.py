import src.utils.callbackUtils as cbUtils
import random
from src.utils.Enums import POSSIBLE_PURPOSES

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type":"object", "properties":{
    "key": {"type": "string"}
}, "required":["key"]})
def save_event_data(data:cbUtils.CallbackDatapack):

    if hasattr(data.event, data.parameter["key"]):
        data.parameter["value"] = getattr(data.event, data.parameter["key"])
        save_data(data)

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={
"type":"object", "properties":{
    "key": {"type": "string"},
    "value":{},
    "locations":{"onfOf":[{"type":"string","enum":["session","node"]},{"type":"array", "items":{"type":"string","enum":["session","node"]}}]}
}, "required":["key", "value"]})
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

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def debugging_false_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])
def debugging_true_filter(data:cbUtils.CallbackDatapack):
    return False

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.FILTER], has_parameter="always", schema={"type":"number"})
def random_chance(data:cbUtils.CallbackDatapack):
    num = random.random()
    return num < data.parameter

dialog_func_info = {save_event_data:{}, debugging_false_filter:{}, debugging_true_filter:{}, save_data:{}, random_chance:{}}

