import discord
from discord import ui, InteractionType, Interaction
from datetime import datetime, timedelta
import Examples.DiscordUtils as DiscordUtils
import src.DialogNodes.BaseType as BaseType

async def send_message(active_node, event, settings):
    '''sends a discord message with provided settings, can handle redirecting to another channel'''
    #TODO: test
    to_send_bits = DiscordUtils.build_discord_message(settings["message"], active_node.graph_node.TTL)
    bot = active_node.handler.bot

    channel = bot.fetch_channel(settings["channel_id"])

    sent_message = await channel.send(**to_send_bits)
    sent_msg_info = DiscordUtils.MessageInfo(sent_message, to_send_bits["view"] if "view" in to_send_bits else None)

    if isinstance(event, Interaction) and not event.response.is_done():
        await event.response.send_message(settings["redirect"])
    elif "redirect" in settings:
        await event.channel.send(settings["redirect"])

    DiscordUtils.record_sent_message(active_node, sent_msg_info)

async def send_response(active_node:BaseType.BaseNode, event, message_settings):
    '''sends a Discord message as a response to event, ie will respond to interactions or reply to messages. This limits messages to be sent in
    same Discord channel as event was triggered in. see send_message to change channel

    Parameters
    ---
    active_node - `BaseNode`
        active node instance event is happening on
    event - `discord.Interaction` or `discord.Message`

    message_settings - `dict`'''
    to_send_bits = DiscordUtils.build_discord_message(message_settings, active_node.graph_node.TTL)

    if isinstance(event, Interaction) and not event.response.is_done():
        await event.response.send_message(**to_send_bits)
        sent_message = await event.original_response()
    else:
        sent_message = await event.channel.send(**to_send_bits)

    sent_msg_info = DiscordUtils.MessageInfo(sent_message, to_send_bits["view"] if "view" in to_send_bits else None)

    DiscordUtils.record_sent_message(active_node, sent_msg_info)
    
async def clear_buttons(active_node, event, goal_node = None, close_messages=None):
    if hasattr(active_node, "focal_message") and active_node.focal_message.view is not None:
        active_node.focal_message.view.stop()

    if close_messages is not None and "timeout" in close_messages and event["timed_out"]:
        await active_node.focal_message.message.edit(content=close_messages["timeout"], view = None)
    elif close_messages is not None and "default" in close_messages:
        await active_node.focal_message.message.edit(content=close_messages["default"], view = None)
    else:
        await active_node.focal_message.message.edit(view = None)

def clicked_this_menu(active_node, event):
    if not hasattr(active_node, "focal_message") or active_node.focal_message is None:
        return False
    return event.message.id == active_node.focal_message.message.id

async def remove_message(active_node, event):
    if hasattr(active_node, "focal_message") and active_node.focal_message is not None:
        await active_node.focal_message.message.delete()
        active_node.focal_message.deleted = True
        if active_node.focal_message.view is not None: 
            active_node.focal_message.view.stop()

        active_node.focal_message = None
    
    if hasattr(active_node, "secondary_messages") and active_node.secondary_messages is not None:
        for message_info in active_node.secondary_messages:
            await message_info.message.delete()
            message_info.deleted = True
            if message_info.view is not None: 
                message_info.view.stop()
        active_node.secondary_messages.clear()

def button_is(active_node, event, goal_node, custom_ids):
    '''checks if button event is one of allowed ones passed in custom_ids'''
    if isinstance(custom_ids, str):
        return event.data["custom_id"] == custom_ids
    else:
        return event.data["custom_id"] in custom_ids

def is_session_user(active_node, event, goal_node=None):
    if active_node.session is None or "user" not in active_node.session:
        return False
    if isinstance(event, Interaction):
        return active_node.session["user"].id == event.user.id
    else:
        return active_node.session["user"].id == event.author.id
    
def session_link_user(active_node, event, goal_node):
    if goal_node.session is None:
        return
    if isinstance(event, Interaction):
        goal_node.session["user"] = event.user
    else: 
        goal_node.session["user"] = event.author

def is_reply(active_node, event, settings=None):
    secondary_categories = settings["categories"] if settings is not None else []
    print("temp debugging of is_reply", event)
    if event.reference.message_id == active_node.focal_message.message.id:
        return True
    if "secondary" in secondary_categories:
        if event.reference.message_id in [msg_info.message.id for msg_info in active_node.secondary_messages]:
            return True
    if "managed_replies" in secondary_categories:
        return event.reference.message_id in [msg_info.message.id for msg_info in active_node.managed_replies]
    return False

def selection_is(active_node, event, settings, goal_node=None):
    print(event.data)
    if event.data["component_type"] != discord.ComponentType.select.value:
        return False
    if event.data["custom_id"] != settings["custom_id"]:
        return False
    return len(event.data["values"]) == 1 and event.data["values"][0] == settings["selection"]

dialog_func_info = {send_response:["callback"], send_message:["callback"], clear_buttons:["callback", "transition_callback"], 
                    clicked_this_menu:["filter"], button_is:["transition_filter"], remove_message:["callback"], 
                    is_session_user:["filter", "transition_filter"],session_link_user: ["transition_callback"],
                    is_reply:["filter"], selection_is:["filter", "transition_filter"]}