import discord
from discord import ui, InteractionType, Interaction
import Extensions.Discord.DiscordMessagingFuncs as DiscordFuncs
import Extensions.Discord.DiscordNode as DiscordNodeType
import src.utils.CallbackUtils as cbUtils
import Extensions.Discord.DiscordUtils as DiscordUtils
from src.utils.Enums import POSSIBLE_PURPOSES


# Yep these functions are less generalized, probably similar to what another developer would want to add if customizing

def save_survey_answer(data:cbUtils.CallbackDatapack):
    active_node:DiscordNodeType.DiscordNode = data.active_node
    goal_node:DiscordNodeType.DiscordNode = data.goal_node
    event = data.event
    settings = data.base_parameter

    target_locations = settings["save_locations"]
    survey_name = settings["survey_name"]

    if isinstance(target_locations, str):
        target_locations = [target_locations]

    to_save_data = {}
    if isinstance(event, discord.Message):
        to_save_data[settings["key"]] = event.content
    else:
        if event.data["component_type"] == discord.ComponentType.button.value:
            to_save_data[settings["key"]] = event.data["custom_id"]
        elif event.data["component_type"] == discord.ComponentType.select.value:
            to_save_data[settings["key"]] = event.data["values"]

    if "current_session" in target_locations and active_node.session is not None:
        if survey_name not in active_node.session.data:
            active_node.session.data[survey_name] = {}
        active_node.session.data[survey_name].update(to_save_data)
    if "next_session" in target_locations and goal_node is not None and goal_node.session is not None:
        if survey_name not in goal_node.session.data:
            goal_node.session.data[survey_name] = {}
        goal_node.session.data[survey_name].update(to_save_data)
cbUtils.set_callback_settings(save_survey_answer, allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key='always', schema={"type": "object", "properties":{ 
    "survey_name": {"type": "string"},
    "key": {"type": "string"},
    "save_locations": {"onfOf":[{"type": "string", "enum":["current_session", "next_session"]}, {"type":"array", "items": {"type": "string", "enum":["current_session", "next_session"]}}]}
    }, "required": ["survey_name", "key", "save_locations"]
})
    
async def report_survey_ansers(data:cbUtils.CallbackDatapack):
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    settings = data.base_parameter
    
    if active_node.session is None:
        return
    message_to_send = "Here is what you responded:\n"+ "\n".join([k+": "+str(v) for k,v in active_node.session.data[settings["survey_name"]].items()])
    data.base_parameter = {"ping_with_reply": True, "message":{"content":message_to_send}, "menu_name": settings["survey_name"]+"_report"}
    await DiscordFuncs.send_message(data)
cbUtils.set_callback_settings(report_survey_ansers, allowed_purposes=[POSSIBLE_PURPOSES.ACTION], runtime_input_key='always', schema={"type": "object", "properties":{ 
    "survey_name": {"type": "string"}}, "required": ["survey_name"]
})


dialog_func_info= {save_survey_answer:{}, report_survey_ansers:{}}