import discord
from discord import ui, InteractionType, Interaction
from datetime import datetime, timedelta
import Examples.DiscordUtils as DiscordUtils
import src.DialogNodes.BaseType as BaseType

async def edit_message(active_node, event, settings):
    '''callback function that edits the discord messsage for this node's menu message, or sends a new one if it doesn't exist. 
    Each node has one menu message that represents what message it is waiting for interactions or replies on'''
    #TODO: test
    if not hasattr(active_node, "menu_message") or active_node.menu_message is None:
        # print(f"edit message callback found no menu message recorded for active node id'd <{id(active_node)}><{active_node.graph_node.id}>")
        await send_message(active_node, event, settings)
        return
    to_send_bits = DiscordUtils.build_discord_message(settings["message"], active_node.graph_node.TTL)
    if isinstance(event, Interaction):
        if not event.response.is_done():
            # print(f"callback using interation event. response is not done")
            await event.response.edit_message(**to_send_bits)
        else:
            # print(f"callback using interation event. ERROR? response done already")
            await active_node.menu_message.message.edit(**to_send_bits)

    else:
        await active_node.menu_message.message.edit(**to_send_bits)
    if "view" in to_send_bits:
        active_node.menu_message.view.stop()
        active_node.menu_message.view = to_send_bits["view"]

async def send_message(active_node, event, settings):
    '''callback function that sends a discord message with provided settings, can handle redirecting to another channel.'''
    #TODO: test
    message_components = DiscordUtils.build_discord_message(settings["message"], active_node.graph_node.TTL)
    bot = active_node.handler.bot

    if "redirect" in settings:
        # meant to send main message to another channel
        channel = await bot.fetch_channel(settings["redirect"]["dest_channel_id"])
        sent_message = await channel.send(**message_components)

        sent_msg_info = DiscordUtils.MessageInfo(sent_message, message_components["view"] if "view" in message_components else None)
        DiscordUtils.record_sent_message(active_node, sent_msg_info, "menu" in settings and settings["menu"])

        message_components = DiscordUtils.build_discord_message(settings["redirect"]["message"], active_node.graph_node.TTL)

    if isinstance(event, Interaction):
        if not event.response.is_done():
            #TODO: ephemeral message support
            await event.response.send_message(**message_components)
            sent_message = await event.original_response()
        else:
            sent_message = await event.channel.send(**message_components)
    else:
        if "use_reply" in settings and settings["use_reply"]:
            sent_message = await event.reply(**message_components)
        else:
            sent_message = await event.channel.send(**message_components)

    sent_msg_info = DiscordUtils.MessageInfo(sent_message, message_components["view"] if "view" in message_components else None)
    DiscordUtils.record_sent_message(active_node, sent_msg_info, "menu" in settings and settings["menu"] and "redirect" not in settings)
    
async def clear_buttons(active_node, event, goal_node = None, close_messages=None):
    '''callback or transition callback function clears all interactable components from message and if there are suboptions for it, changes the Discord message's contents
    to the provided messages (to help show oh no we're closed now)'''
    if hasattr(active_node, "menu_message") and active_node.menu_message.view is not None:
        active_node.menu_message.view.stop()

    if close_messages is not None and "timeout" in close_messages and event["timed_out"]:
        await active_node.menu_message.message.edit(content=close_messages["timeout"], view = None)
    elif close_messages is not None and "default" in close_messages:
        await active_node.menu_message.message.edit(content=close_messages["default"], view = None)
    else:
        await active_node.menu_message.message.edit(view = None)

def clicked_this_menu(active_node, event):
    '''filter function that checks if event (should be an interaction) interacted on this node's menu message'''
    if not hasattr(active_node, "menu_message") or active_node.menu_message is None:
        return False
    return event.message.id == active_node.menu_message.message.id

async def remove_message(active_node, event):
    '''callback function that deletes all discord messages recorded as menu or secondary in node. secondary should be supplementary messages sent by bot'''
    if hasattr(active_node, "menu_message") and active_node.menu_message is not None:
        await active_node.menu_message.message.delete()
        active_node.menu_message.deleted = True
        if active_node.menu_message.view is not None: 
            active_node.menu_message.view.stop()

        active_node.menu_message = None
    
    if hasattr(active_node, "secondary_messages") and active_node.secondary_messages is not None:
        for message_info in active_node.secondary_messages:
            await message_info.message.delete()
            message_info.deleted = True
            if message_info.view is not None: 
                message_info.view.stop()
        active_node.secondary_messages.clear()

def button_is(active_node, event, custom_ids, goal_node=None):
    '''filter or transition function checks if button event is one of allowed ones passed in custom_ids'''
    if isinstance(custom_ids, str):
        return event.data["custom_id"] == custom_ids
    else:
        return event.data["custom_id"] in custom_ids

def is_session_user(active_node, event, goal_node=None):
    '''filter or transition filter function that checks if the user for the interaction or message event is the same one as what is recorded in the 
    ndoe's session.'''
    if active_node.session is None or "user" not in active_node.session.data:
        return False
    if isinstance(event, Interaction):
        return active_node.session.data["user"].id == event.user.id
    else:
        return active_node.session.data["user"].id == event.author.id
    
def session_link_user(active_node, event, goal_node):
    '''transition callback function that records the user that triggered the interaction or message event as the owner of the session'''
    if goal_node.session is None:
        return
    if isinstance(event, Interaction):
        goal_node.session.data["user"] = event.user
    else: 
        goal_node.session.data["user"] = event.author

def is_reply(active_node, event, settings=None):
    '''filter function that checks if message event is replying to menu message, with settings to check if it is a reply to secondary or reply messages'''
    secondary_categories = settings["categories"] if settings is not None else []
    # print("temp debugging of is_reply", event)
    if event.reference.message_id == active_node.menu_message.message.id:
        return True
    if "secondary" in secondary_categories:
        if event.reference.message_id in [msg_info.message.id for msg_info in active_node.secondary_messages]:
            return True
    if "managed_replies" in secondary_categories:
        return event.reference.message_id in [msg_info.message.id for msg_info in active_node.managed_replies]
    return False

def selection_is(active_node, event, settings, goal_node=None):
    '''filter or transition filter function that checks if the selection menu interaction is choosing a specific value'''
    # print(event.data)
    if event.data["component_type"] != discord.ComponentType.select.value:
        return False
    if event.data["custom_id"] != settings["custom_id"]:
        return False
    return len(event.data["values"]) == 1 and event.data["values"][0] == settings["selection"]

def transfer_menu(active_node, event, next_node):
    '''transition callback function that moves the menu message from this node to the next node so the next node can edit the message instead of 
    sending a new one'''
    DiscordUtils.record_sent_message(next_node, active_node.menu_message, is_menu=True)
    active_node.menu_message = None

def setup_DMM_node(active_node, event):
    '''double checks node is setup for discord message menu functionality (aka the operations in this file)
    if something like this is needed, really a new node type should be defined.'''
    if not hasattr(active_node, "secondary_messages"):
        active_node.secondary_messages = set()
    if not hasattr(active_node, "menu_message"):
        active_node.menu_message = None
    if not hasattr(active_node, "managed_replies"):
        active_node.managed_replies = set()

#TODO: INVESTIGATE potentially a decorator to add settings to function as attributes? attributes on functions should be technically possible
dialog_func_info = {send_message:["callback"], clear_buttons:["callback", "transition_callback"], 
                    clicked_this_menu:["filter"], button_is:["transition_filter", "filter"], remove_message:["callback"], 
                    is_session_user:["filter", "transition_filter"],session_link_user: ["transition_callback"],
                    is_reply:["filter"], selection_is:["filter", "transition_filter"], edit_message:["callback"],
                    transfer_menu:["transition_callback"], setup_DMM_node:["callback"]}