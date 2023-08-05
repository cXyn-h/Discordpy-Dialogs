import discord
from discord import ui, InteractionType, Interaction
from datetime import datetime, timedelta

async def send_message(active_node, event, message_settings):
    #TODO:
    bot = active_node.handler.bot

async def send_response(active_node, event, message_settings):
    #TODO: add embeds
    view = None
    if "components" in message_settings and len(message_settings["components"]) > 0:
        view = ui.View(timeout=active_node.graph_node.TTL)
        for component in message_settings["components"]:
            #TODO: allow more options than buttons
            view.add_item(ui.Button(**component))

    if isinstance(event, Interaction) and not event.response.is_done():
        if view is not None:
            await event.response.send_message(content = message_settings["content"], view = view)
        else:
            await event.response.send_message(content = message_settings["content"])
        sent_message = await event.original_response()
    else:
        if view is not None:
            sent_message = await event.channel.send(content = message_settings["content"], view = view)
        else:
            sent_message = await event.channel.send(content = message_settings["content"])
    #TODO: doing this assignment limits to only being able to use this function once in only entering callbacks. any better ways?
    active_node.message = sent_message
    active_node.view = view

async def clear_buttons(active_node, event, goal_node = None, close_messages=None):
    if active_node.view and active_node.view is not None:
        active_node.view.stop()
    if active_node.message:
        if close_messages is not None and "timeout" in close_messages and event["timed_out"]:
            await active_node.message.edit(content=close_messages["timeout"], view = None)
        elif close_messages is not None and "default" in close_messages:
            await active_node.message.edit(content=close_messages["default"], view = None)
        else:
            await active_node.message.edit(view = None)

def clicked_this_menu(active_node, event):
    if not hasattr(active_node, "message") or active_node.message is None:
        return False
    return event.message.id == active_node.message.id

async def remove_message(active_node, event):
    if active_node.message and active_node.message is not None:
        await active_node.message.delete()
        active_node.message = None

def button_is(active_node, event, goal_node, custom_ids):
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

dialog_func_info = {send_response:["callback"], send_message:["callback"], clear_buttons:["callback", "transition_callback"], 
                    clicked_this_menu:["filter"], button_is:["transition_filter"], remove_message:["callback"], 
                    is_session_user:["filter", "transition_filter"],session_link_user: ["transition_callback"]}