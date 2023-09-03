import src.utils.callbackUtils as cbUtils
import random

@cbUtils.callback_settings(allowed=["callback", "transition_callback"], has_parameter="always")
def save_event_data(active_node, event, settings, goal_node=None):
    if hasattr(event, settings["key"]):
        settings["value"] = getattr(event, settings["key"])
        save_data(active_node, event, settings, goal_node)

@cbUtils.callback_settings(allowed=["callback", "transition_callback"], has_parameter="always")
def save_data(active_node, event, settings, goal_node=None):
    locations = settings["locations"]
    node = goal_node
    if goal_node is None:
        node = active_node

    print(f"saving data, key <{settings['key']}>, value <{settings['value']}> locations <{settings['locations']}>")
    if (locations == "session" or "session" in locations) and node.session is not None:
        node.session.data[settings["key"]] = settings["value"]
        print(f"after saving to session, data is now <{node.session.data}>")
    if (locations == "node" or "node" in locations):
        setattr(node, settings["key"], settings["value"])
        print(f"after saving to node, node has property value: <{getattr(node, settings['key'])}>")

@cbUtils.callback_settings(allowed=["filter", "transition_filter"])
def debugging_false_filter(active_node, event, goal_node=None):
    return False

@cbUtils.callback_settings(allowed=["filter", "transition_filter"])
def debugging_true_filter(active_node, event, goal_node=None):
    return False

@cbUtils.callback_settings(allowed=["filter"], has_parameter="always")
def random_chance(active_node, event, proportion):
    num = random.random()
    return num < proportion

dialog_func_info = {save_event_data:{}, debugging_false_filter:{}, debugging_true_filter:{}, save_data:{}, random_chance:{}}

