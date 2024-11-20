import src.utils.CallbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES
import asyncio
@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], description_blurb="internally acknowledge something happened")
def debugging_action(data:cbUtils.CallbackDatapack):
    print(f"DEBUGGING ACTION!! For node <{id(data.active_node)}><{data.active_node.graph_node.id}> event <{id(data.event)}><{type(data.event)}>")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], schema={"type": "number"})
async def wait(datapack:cbUtils.CallbackDatapack):
    time = int(datapack.base_parameter)
    await asyncio.sleep(time)

dialog_func_info = {debugging_action:{}, wait:{}}

