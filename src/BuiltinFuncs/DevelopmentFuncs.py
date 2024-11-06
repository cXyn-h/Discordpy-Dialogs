import src.utils.CallbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES
@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], description_blurb="internally acknowledge something happened")
def debugging_action(data:cbUtils.CallbackDatapack):
    print(f"DEBUGGING ACTION!! For node <{id(data.active_node)}><{data.active_node.graph_node.id}> event <{id(data.event)}><{type(data.event)}>")

dialog_func_info = {debugging_action:{}}

