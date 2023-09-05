import discord
from discord import ui, InteractionType, Interaction

from datetime import datetime, timedelta

import Examples.DiscordUtils as DiscordUtils
import src.DialogNodes.BaseType as BaseType
import src.utils.callbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES

async def edit_message(active_node, event, settings):
    '''callback function that edits the discord messsage for this node's menu message, or sends a new one if it doesn't exist. 
    Each node has one menu message that represents what message it is waiting for interactions or replies on'''
    # print(f"edit message function called, active node <{id(active_node)}><{active_node.graph_node.id}> event is <{event}>, parameters is <{settings}>")
    if not hasattr(active_node, "menu_message") or active_node.menu_message is None:
        # print(f"edit message callback found no menu message recorded for active node id'd <{id(active_node)}><{active_node.graph_node.id}>")
        await send_message(active_node, event, settings)
        return
    
    to_send_bits = DiscordUtils.build_discord_message(settings["message"], active_node.graph_node.TTL, default_fills={"view":None})
    if isinstance(event, Interaction):
        if not event.response.is_done():
            # print(f"callback using interation event. response is not done")
            # to make sure there's no interaction failed message, which would be confusing, filter it out and do response.
            await event.response.edit_message(**to_send_bits)
        else:
            print(f"weird state. edit message called using interation event. response has been done already")
            await active_node.menu_message.message.edit(**to_send_bits)
    else:
        await active_node.menu_message.message.edit(**to_send_bits)

    if "view" in to_send_bits:
        active_node.menu_message.view.stop()
        active_node.menu_message.view = to_send_bits["view"]
cbUtils.set_callback_settings(edit_message, has_parameter="always", allowed=[POSSIBLE_PURPOSES.ACTION])

async def send_DM(active_node, event, settings):
    if isinstance(event, Interaction):
        user = event.user
    else:
        user = event.author
    
    dm_channel = user.dm_channel
    if dm_channel == None:
        dm_channel = await user.create_dm()

    if "redirect" not in settings:
        settings["redirect"] = {}
    settings["redirect"]["dest_channel_id"] = dm_channel.id
    await send_message(active_node, event, settings)
cbUtils.set_callback_settings(send_DM, has_parameter="always", allowed=[POSSIBLE_PURPOSES.ACTION])

async def send_message(active_node, event, settings):
    '''callback function that sends a discord message with provided settings, can handle redirecting to another channel.'''
    message_components = DiscordUtils.build_discord_message(settings["message"], active_node.graph_node.TTL)
    bot = active_node.handler.bot

    if "redirect" in settings:
        # means want to send main message to another channel. special case where extra message is sent 
        #   elsewhere but still could send something in same channel as usual
        channel = await bot.fetch_channel(settings["redirect"]["dest_channel_id"])
        sent_message = await channel.send(**message_components)

        sent_msg_info = DiscordUtils.MessageInfo(sent_message, message_components["view"] if "view" in message_components else None)
        DiscordUtils.record_sent_message(active_node, sent_msg_info, "menu" in settings and settings["menu"])

        # optionally can specify a message to reply with to og message to indicate redirected to another place. 
        if "message" in settings["redirect"]:
            message_components = DiscordUtils.build_discord_message(settings["redirect"]["message"], active_node.graph_node.TTL)
        else:
            # don't need to do second half of method in this case so early return
            return

    # sending message in same channel as original event. either for redirect message or original when no redirects
    if isinstance(event, Interaction):
        if not event.response.is_done():
            #TODO: ephemeral message support? might mess with storing message in node data?
            await event.response.send_message(**message_components)
            sent_message = await event.original_response()
        else:
            sent_message = await event.channel.send(**message_components)
    else:
        if "use_reply" in settings:
            print(f"using reply, will it ping? {True if settings['use_reply'] == 'ping' else False}")
            sent_message = await event.reply(**message_components, allowed_mentions=discord.AllowedMentions(replied_user=True if settings["use_reply"] == "ping" else False))
        else:
            sent_message = await event.channel.send(**message_components)

    sent_msg_info = DiscordUtils.MessageInfo(sent_message, message_components["view"] if "view" in message_components else None)
    DiscordUtils.record_sent_message(active_node, sent_msg_info, "menu" in settings and settings["menu"] and "redirect" not in settings)
cbUtils.set_callback_settings(send_message, has_parameter="always", allowed=[POSSIBLE_PURPOSES.ACTION])

async def clear_buttons(active_node, event, goal_node = None, close_messages=None):
    '''callback or transition callback function clears all interactable components from message and if there are suboptions for it, changes the Discord message's contents
    to the provided messages (to help show oh no we're closed now)'''
    if not hasattr(active_node, "menu_message") or active_node.menu_message is None:
        return
    
    if hasattr(active_node, "menu_message") and active_node.menu_message.view is not None:
        active_node.menu_message.view.stop()

    if close_messages is not None and "timeout" in close_messages and event["timed_out"]:
        await active_node.menu_message.message.edit(content=close_messages["timeout"], view = None)
    elif close_messages is not None and "default" in close_messages:
        await active_node.menu_message.message.edit(content=close_messages["default"], view = None)
    else:
        await active_node.menu_message.message.edit(view = None)
cbUtils.set_callback_settings(clear_buttons, has_parameter="optional", allowed=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION])

def clicked_this_menu(active_node, event):
    '''filter function that checks if event (should be an interaction) interacted on this node's menu message'''
    if not hasattr(active_node, "menu_message") or active_node.menu_message is None:
        return False
    return event.message.id == active_node.menu_message.message.id
cbUtils.set_callback_settings(clicked_this_menu, allowed=[POSSIBLE_PURPOSES.FILTER])

async def remove_message(active_node, event, settings=None):
    '''callback function that deletes all discord messages recorded as menu or secondary in node. secondary should be supplementary messages sent by bot'''
    if settings is None:
        settings = ["menu", "secondary"]
    if (settings == "menu" or "menu" in settings) and hasattr(active_node, "menu_message") and active_node.menu_message is not None:
        await active_node.menu_message.message.delete()
        active_node.menu_message.deleted = True
        if active_node.menu_message.view is not None: 
            active_node.menu_message.view.stop()

        active_node.menu_message = None
    
    if (settings == "secondary" or "secondary" in settings) and hasattr(active_node, "secondary_messages") and active_node.secondary_messages is not None:
        for message_info in active_node.secondary_messages:
            await message_info.message.delete()
            message_info.deleted = True
            if message_info.view is not None: 
                message_info.view.stop()
        active_node.secondary_messages.clear()
cbUtils.set_callback_settings(remove_message, allowed=[POSSIBLE_PURPOSES.ACTION], has_parameter="optional")

def button_is(active_node, event, custom_ids, goal_node=None):
    '''filter or transition function checks if button event is one of allowed ones passed in custom_ids'''
    if isinstance(custom_ids, str):
        return event.data["custom_id"] == custom_ids
    else:
        return event.data["custom_id"] in custom_ids
cbUtils.set_callback_settings(button_is, has_parameter="always", allowed=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.FILTER])

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.FILTER])
def is_session_user(active_node, event, goal_node=None):
    '''filter or transition filter function that checks if the user for the interaction or message event is the same one as what is recorded in the 
    ndoe's session.'''
    if active_node.session is None or "user" not in active_node.session.data:
        return False
    if isinstance(event, Interaction):
        return active_node.session.data["user"].id == event.user.id
    else:
        return active_node.session.data["user"].id == event.author.id

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.TRANSITION_ACTION, POSSIBLE_PURPOSES.ACTION])  
def session_link_user(active_node, event, goal_node=None):
    '''transition callback function that records the user that triggered the interaction or message event as the owner of the session'''
    if goal_node is None:
        session = active_node.session
    else:
        session = goal_node.session

    if session is None:
        return
    
    if isinstance(event, Interaction):
        session.data["user"] = event.user
    else: 
        session.data["user"] = event.author

@cbUtils.callback_settings(has_parameter="optional", allowed=[POSSIBLE_PURPOSES.FILTER])  
def is_reply(active_node, event, settings=None):
    '''filter function that checks if message event is replying to menu message, with settings to check if it is a reply to secondary or reply messages'''
    secondary_categories = settings["categories"] if settings is not None else []
    # print("temp debugging of is_reply", event)
    if event.reference is not None and event.reference.message_id == active_node.menu_message.message.id:
        return True
    if "secondary" in secondary_categories:
        if event.reference is not None and  event.reference.message_id in [msg_info.message.id for msg_info in active_node.secondary_messages]:
            return True
    if "managed_replies" in secondary_categories:
        return event.reference is not None and event.reference.message_id in [msg_info.message.id for msg_info in active_node.managed_replies]
    return False

@cbUtils.callback_settings(has_parameter="always", allowed=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER])  
def selection_is(active_node, event, settings, goal_node=None):
    '''filter or transition filter function that checks if the selection menu interaction is choosing a specific value'''
    # print(event.data)
    if event.data["component_type"] != discord.ComponentType.select.value:
        return False
    if event.data["custom_id"] != settings["custom_id"]:
        return False
    return len(event.data["values"]) == 1 and event.data["values"][0] == settings["selection"]

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.TRANSITION_ACTION])  
def transfer_menu(active_node, event, goal_node):
    '''transition callback function that moves the menu message from this node to the next node so the next node can edit the message instead of 
    sending a new one'''
    DiscordUtils.record_sent_message(goal_node, active_node.menu_message, is_menu=True)
    active_node.menu_message = None
    print(f"transferred menu from <{id(active_node)}><{active_node.graph_node.id}> to <{id(goal_node)}><{goal_node.graph_node.id}>")

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.ACTION])  
def setup_DMM_node(active_node, event):
    '''double checks node is setup for discord message menu functionality (aka the operations in this file)
    if something like this is needed, really a new node type should be defined.'''
    if not hasattr(active_node, "secondary_messages"):
        active_node.secondary_messages = set()
    if not hasattr(active_node, "menu_message"):
        active_node.menu_message = None
    if not hasattr(active_node, "managed_replies"):
        active_node.managed_replies = set()

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], has_parameter="Optional")
def is_server_member(active_node, event, goal_node=None, server_id=None):
    if (active_node.session is None or "server_id" not in active_node.session.data or active_node.session.data["server_id"] is None) and server_id is None:
        return False
    
    if server_id is None:
        server_id = active_node.session.data["server_id"]
    
    bot = active_node.handler.bot
    server = bot.get_guild(server_id)
    if server is None:
        return False
    
    if isinstance(event, Interaction):
        user = event.user
    else:
        user = event.author
    return server.get_member(user.id) is None

dialog_func_info = {send_message:{}, clear_buttons:{}, 
                    clicked_this_menu:{}, button_is:{}, remove_message:{}, 
                    is_session_user:{}, session_link_user:{},
                    is_reply:{}, selection_is:{}, edit_message:{},
                    transfer_menu:{}, setup_DMM_node:{}, send_DM:{}, is_server_member:{}}