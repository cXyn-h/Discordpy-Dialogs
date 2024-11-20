import discord
from discord import ui, InteractionType, Interaction
from discord.ext.commands import Context

from datetime import datetime, timedelta
import copy

import Extensions.Discord.DiscordUtils as DiscordUtils
import Extensions.Discord.DiscordNode as DiscordNodeType
import src.DialogNodes.BaseType as BaseType
import src.BuiltinFuncs.BaseFuncs as NodetionBaseFuncs
import src.utils.CallbackUtils as cbUtils
import src.utils.SchemaUtils as SchemaUtils
from src.utils.Enums import POSSIBLE_PURPOSES

import logging
import src.utils.LoggingHelper as logHelper
discord_logger = logging.getLogger('Discord Callbacks')
logHelper.use_default_setup(discord_logger)
discord_logger.setLevel(logging.INFO)

ALL_MENUS_KEY = "*all_menus"
ALL_REPLIES_KEY = "*all_replies"

DISCORD_MESSAGE_SCHEMA_PACK = ["Schemas/message.yml", "Schemas/poll.yml", "Schemas/embed.yml", "Schemas/messageComponent.yml"]

def merge_message_settings(base, addon):
    '''takes two sets of messages and their sending options and moves settings in addon into base. Overwrites simple types, adds on to lists'''
    for setting in ["menu_name", "dest_channel_id", "ping_with_reply", "reply_to", "ephemeral", "silent"]:
        if setting in addon:
            base[setting] = addon[setting]
    if "redirect_message" in addon:
        if "redirect_message" not in base:
            base["redirect_message"] = {}
        if "content" in addon["redirect_message"]:
            base["redirect_message"]["content"] = addon["redirect_message"]["content"]
        for setting in ["components", "embeds", "attachments", "stickers"]:
            if setting in addon["redirect_message"]:
                if setting not in base["redirect_message"]:
                    base["redirect_message"][setting] = []
                base["redirect_message"][setting].extend(addon["redirect_message"][setting])
    if "message" in addon:
        if "message" not in base:
            base["message"] = {}
        if "content" in addon["message"]:
            base["message"]["content"] = addon["message"]["content"]
        for setting in ["components", "embeds", "attachments", "stickers"]:
            if setting in addon["message"]:
                if setting not in base["message"]:
                    base["message"][setting] = []
                base["message"][setting].extend(addon["message"][setting])
    return base

async def gather_send_message_settings(data:cbUtils.CallbackDatapack, settings, message_components):
    '''organizes settings to pass to send message using passed in data'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    bot = data.bot

    # first thing is finding channel object to send message to
    dest_channel = None
    try:
        if "dest_channel" in settings and isinstance(settings["dest_channel"], discord.TextChannel):
            # special override allowed for callbacks to just pass a channel object to send in
            dest_channel = settings["dest_channel"]
            discord_logger.debug(f"dest channel was overridden in settings <{dest_channel}>")
        elif "dest_channel_id" in settings:
            discord_logger.debug(f"dest channel is id. searching given value <{settings['dest_channel_id']}>")
            # either just a prefix "dm:" or "pm:", prefix and then user id, or no prefix and is channel id (dm or otherwise)
            if isinstance(settings["dest_channel_id"], str) and settings["dest_channel_id"].find(":") > -1:
                # if is string and using special formatting
                discord_logger.debug(f"dest channel id is dm for user")
                if len(settings["dest_channel_id"]) > 3:
                    try:
                        user_id = int(settings["dest_channel_id"][settings["dest_channel_id"].find(":")+1:])
                    except ValueError as e:
                        discord_logger.warning(f"invalid value passed as userid")
                        return
                    user:discord.User = bot.get_user(user_id)
                    if user is None:
                        discord_logger.debug(f"tried parsing id in settings, but user is invalid")
                        # not valid userid, or other connection issue
                        return
                else:
                    # just has prefix, assuming dm the person that caused the event
                    if isinstance(event, Interaction):
                        user = event.user
                    elif isinstance(event, discord.Message) or isinstance(event, Context):
                        user = event.author
                    else:
                        discord_logger.warning(f"send message not given valid event type to get user for dm channel cause not specified in settings")
                        return None
                dest_channel = user.dm_channel
                if dest_channel == None:
                    dest_channel = await user.create_dm()
            else:
                dest_channel = bot.get_channel(int(settings["dest_channel_id"]))
                discord_logger.debug(f"dest channel id in settings doesn't need to be split, found channel is <{dest_channel}>")
        elif "reply_to" in settings:
            if isinstance(settings["reply_to"], str):
                if settings["reply_to"] == "event_message":
                    dest_channel = event.channel
                else:
                    parts = settings["reply_to"].split('/')
                    dest_channel = bot.get_channel(int(parts[-2]))
            else:
                dest_channel = settings["reply_to"].channel
        elif active_node.session is not None and "default_channel" in active_node.session.data:
            dest_channel = bot.get_channel(int(active_node.session.data["default_channel"]))
        elif hasattr(active_node, "default_channel"):
            discord_logger.debug(f"default channel on node found, {getattr(active_node, 'default_channel')}")
            dest_channel = bot.get_channel(int(getattr(active_node, "default_channel")))
        else:
            discord_logger.debug(f"sanity check vars of active node {vars(active_node)}")
            dest_channel = event.channel
            discord_logger.debug(f"no dest channel. defaulting to channel event is from <{dest_channel}>")
    except Exception as e:
        discord_logger.error(f"SOMETHING REALLY BAD IN SEND MESSAGE {e}")

    if dest_channel is None or not isinstance(dest_channel, discord.TextChannel):
        raise Exception(f"send message early found that dest channel is invalid")
        # invalid id or other issue fetching channel object

    reference = None
    discord_logger.debug(f"settings keys {settings.keys()} chosen dest_channel {dest_channel.id}")
    # gathering what message to reply to. only set if its in the same channel as where we intend to send to
    if "reply_to" in settings:
        discord_logger.debug(f"trying to retrieve reference message for sending, settings {settings['reply_to']}")
        try: 
            if isinstance(settings["reply_to"], str):
                if settings["reply_to"] == "event_message":
                    discord_logger.debug(f"using event message")
                    if event.channel.id == dest_channel.id:
                        if isinstance(event, discord.Message):
                            reference = event
                        elif isinstance(event, Interaction) or isinstance(event, Context):
                            reference = event.message
                else:
                    discord_logger.debug(f"splitting jump link for reference message")
                    parts = settings["reply_to"].split('/')
                    if int(parts[-2]) == dest_channel.id:
                        discord_logger.debug(f"reply split is ready to set reference.")
                        reference = dest_channel.get_partial_message(int(parts[-1]))
                        discord_logger.debug(f"reference is {reference.id}")
            elif settings["reply_to"].channel.id == dest_channel.id:
                reference = settings["reply_to"]
        except Exception as e:
            discord_logger.warning(f"tried to get reference message, but failed. ignoring it, {e}")
    
    send_settings = message_components
    if reference is not None:
        discord_logger.debug(f"reference of next sent message is {type(reference)} {reference.jump_url}")
        send_settings.update({"reference": reference.to_reference()})
    if "ping_with_reply" in settings:
        send_settings.update({"allowed_mentions": discord.AllowedMentions(replied_user=settings["ping_with_reply"])})
    if "silent" in settings:
        send_settings.update({"silent": settings["silent"]})
    if "ephemeral_interaction" in settings:
        send_settings.update({"ephemeral": settings["ephemeral_interaction"]})
    if "ephemeral" in settings:
        send_settings.update({"ephemeral": settings["ephemeral"]})
    return dest_channel, send_settings

#TODO: add checks to make sure there is a valid set of data after combining message settings from yaml and overrides
async def send_message(data:cbUtils.CallbackDatapack):
    '''callback function that sends a discord message with provided settings.'''
    # main operation is trying to send message under given menu name. with additional setting of interaction response if possible and wanted
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    discord_logger.info(f"send message called on node <{active_node.id}><{active_node.graph_node.id}> event {type(event)}")

    # override yaml with anything that is generated in function_data
    runtime_input_key = "next_message_settings"
    override_settings = NodetionBaseFuncs.default_runtime_input_finder(runtime_input_key, data, default={})
    settings = merge_message_settings(data.base_parameter if data.base_parameter is not None else {}, override_settings)
    message_components = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
    
    discord_logger.debug(f"send message settings chosen are <{settings}>")

    respond_interaction = "respond_interaction" in settings and \
            isinstance(settings["respond_interaction"], bool) and \
            settings["respond_interaction"]
    correction_attempts = 1
    '''number of times to allow trying something different to get message sent'''
    if "correction_attempts" in settings and isinstance(settings["correction_attempts"], int):
        correction_attempts = settings["correction_attempts"]
    menu_name = settings["menu_name"]

    if respond_interaction and isinstance(event, Interaction):
        # this is an interaction and we want to try responding. only case to do the interaction response
        # doing secodary attempts to allow for chained send_message calls for same event that all can attempt to repond to interaction
        # interaction already decides destination and what to reply to
        discord_logger.debug(f"found interaction want to respond to ")
        if "dest_channel_id" in settings:
            del settings["dest_channel_id"]
        if "reply_to" in settings:
            del settings["reply_to"]
        if "dest_channel" in settings:
            del settings["dest_channel"]       
        if event.response.is_done():
            discord_logger.debug(f"found interaction want to respond to and it already was responded to")
            # done means treat regular send/edit, existing menu means check editing
            if "ephemeral_interaction" in settings:
                del settings["ephemeral_interaction"]

            if menu_name in active_node.menu_messages_info:
                discord_logger.debug(f"send message interaction response finds interaction finished and menu already recorded. correction attempts after this {correction_attempts - 1}")
                if correction_attempts > 0:
                    if "silent" in settings:
                        del settings["silent"]
                    correction_attempts -= 1
                    settings["correction_attempts"] = correction_attempts
                    data.base_parameter = settings
                    return await edit_message(data)
                return None
            else:
                if correction_attempts > 0:
                    discord_logger.debug(f"found interaction want to respond to and it already was responded to but want to send a new message")
                    settings["respond_interaction"] = False
                    settings["reply_to"] = "event_message"
                    correction_attempts -= 1
                    settings["correction_attempts"] = correction_attempts
                    # send a message the regular way but make it look the same as it would actual interaction response
                    data.base_parameter = settings
                    return await send_message(data)
        else:
            discord_logger.debug(f"found interaction want to respond to and it doesn't have a response.")
            # interaction not done
            if menu_name in active_node.menu_messages_info:
                discord_logger.debug(f"found interaction want to respond to and it doesn't have a response but menu already exists. trying edit")
                # if menu is the same message as the event's we can try editing using response
                if correction_attempts > 0:
                    if "silent" in settings:
                        del settings["silent"]
                    data.base_parameter = settings
                    correction_attempts -= 1
                    settings["correction_attempts"] = correction_attempts
                    return await edit_message(data)
                return None
            else:
                discord_logger.debug(f"found interaction want to respond to and it doesn't have a response so sending a new message")
                _, send_settings = await gather_send_message_settings(data=data, settings=settings, message_components=message_components)
                # interaction not done and new menu name. so interaction response send message
                dirty = False
                if send_settings["view"] is None:
                    del message_components["view"]
                    dirty = True
                # interaction send_message doesn't like view being null, but message info uses null to mean no view, so remove briefly for send message
                await event.response.send_message(**send_settings)
                if dirty:
                    message_components["view"] = None
                sent_message = await event.original_response()
                sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
                active_node.record_menu_message(settings["menu_name"], sent_message_info)
                data.section_data["previous_message"] = sent_message_info
    else:
        discord_logger.debug(f"send message not responding to interaction")
        # any other case of not responding to interaction, or is not an interaction and don't care about this setting, just send message
        if "ephemeral_interaction" in settings:
            del settings["ephemeral_interaction"]
        if menu_name in active_node.menu_messages_info:
            discord_logger.debug(f"send message not responding to interaction and message already recorded")
            if correction_attempts > 0:
                if "silent" in settings:
                    del settings["silent"]
                if "dest_channel_id" in settings:
                    del settings["dest_channel_id"]
                if "reply_to" in settings:
                    del settings["reply_to"]
                if "dest_channel" in settings:
                    del settings["dest_channel"]
                correction_attempts -= 1
                settings["correction_attempts"] = correction_attempts
                data.base_parameter = settings
                return await edit_message(data)
            # menu already taken and can't edit. nothing can be done
        else:
            discord_logger.debug(f"send message not responding to interaction and message not recorded")
            # if have a setting for where to send passed in, then use that don't get channel from reply stuff
            # if function callbacks already found channel object, let it user secret location dest_channel as backup
            dest_channel, send_settings = await gather_send_message_settings(data=data, settings=settings, message_components=message_components)

            sent_message = await dest_channel.send(**send_settings)
            sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
            active_node.record_menu_message(settings["menu_name"], sent_message_info)
            data.section_data["previous_message"] = sent_message_info
cbUtils.set_callback_settings(send_message, schema="Schemas/sendMessage.yml", runtime_input_key="next_message_settings", allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], reference_schemas=DISCORD_MESSAGE_SCHEMA_PACK)

async def edit_message(data:cbUtils.CallbackDatapack):
    '''callback that edits the menu specified'''

    async def edit_helper(edit_settings, message_info:DiscordUtils.NodetionDCMenuInfo, interaction_mode=False):
        nonlocal data
        event = data.event
        if message_info.deleted:
            discord_logger.warning(f"edit message trying to edit menu <{settings['menu_name']}> but target message already deleted. not doing anything else")
            return
        if interaction_mode:
            await event.response.edit_message(**edit_settings)
            edited_message = await event.original_response()
        else:
            edited_message = await message_info.message.edit(**edit_settings)

        message_info.message = edited_message
        if "view" in edit_settings:
            discord_logger.debug(f"view was specified in message, removing old one")
            # this will most likely be part of message components every call, but leaving in check anyways. need to clean up old view properly
            if message_info.view is not None:
                discord_logger.debug(f"stopping old view")
                message_info.view.stop()
            message_info.view = edit_settings["view"]
        data.section_data["previous_message"] = message_info

    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    bot = data.bot
    discord_logger.info(f"edit message called on node <{active_node.id}><{active_node.graph_node.id}> event handling")

    runtime_input_key = "next_message_settings"
    override_settings = NodetionBaseFuncs.default_runtime_input_finder(runtime_input_key, data, default={})
    settings = merge_message_settings(data.base_parameter if data.base_parameter is not None else {}, override_settings)
    
    discord_logger.debug(f"edit message settings are <{settings}>")

    respond_interaction = "respond_interaction" in settings and \
            isinstance(settings["respond_interaction"], bool) and \
            settings["respond_interaction"]
    correction_attempts = 1
    '''number of times to allow trying something different to get message sent'''
    if "correction_attempts" in settings and isinstance(settings["correction_attempts"], int):
        correction_attempts = settings["correction_attempts"]
    menu_name = settings.get("menu_name", None)
    discord_logger.debug(f"calculated decision fields are responding to interaction <{respond_interaction}> correction attempts left <{correction_attempts}> menu name <{menu_name}>")

    if respond_interaction and isinstance(event, Interaction):
        # this is an interaction and we want to try responding.
        # interaction response edit_message edits the message a component is attached to
        # edit response errors if interaction already responded to
        # only case to do the interaction response
        discord_logger.debug(f"found interaction want to respond to. is done? {event.response.is_done()} type {event.type}")
        if event.response.is_done():
            discord_logger.debug(f"found interaction want to respond to but it already was responded to")
            # response is done already, no way to use interaction response, so going to regular
            if correction_attempts > 0:
                correction_attempts -= 1
                settings["correction_attempts"] = correction_attempts
                settings["respond_interaction"] = False
                data.base_parameter = settings
                return await edit_message(data)
        else:
            discord_logger.debug(f"found interaction want to respond to and it doesn't have a response.")
            # trying to respond to interaction by editing
            if menu_name is None:
                discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name was not provided")
                # no provided menu name to edit, assume want to edit intereaction's response message
                # first step is checking if the interaction message is tracked to know if tracking needs to be updated
                if event.type == InteractionType.component:
                    interaction_message = event.message
                else:
                    # don't think this way would work for other nodes. no response and only thing that has a message attached is a component interaction
                    try:
                        interaction_message = await event.original_response()
                        discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name was not provided, fetched original message")
                    except Exception as e:
                        # means interaction message couldn't be found. no way to find what message to edit or send
                        return
                edit_settings = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
                if "ping_with_reply" in settings:
                    edit_settings.update({"allowed_mentions": discord.AllowedMentions(replied_user=settings["ping_with_reply"])})
                interaction_message_menu_name = active_node.get_menu_name_of(interaction_message.id)
                if interaction_message_menu_name is None:
                    # menu name is none, message that will be edited not being tracked. no way to add tracking
                    return
                else:
                    # found tracking. edit and adjust
                    await edit_helper(edit_settings, active_node.get_menu_info(interaction_message_menu_name), interaction_mode=True)
            else:
                discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name was provided")
                # menu name provided, goal is to edit that message and if possible do it as interaction response
                if menu_name not in active_node.menu_messages_info:
                    discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name is not tracked")
                    # editing not possible. going to send attempting interaction response
                    if correction_attempts > 0:
                        correction_attempts -= 1
                        settings["correction_attempts"] = correction_attempts
                        settings["reply_to"] = "event_message"
                        data.base_parameter = settings
                        return await send_message(data)
                # need to check the menu for the interaction response message is the menu
                # first is grabbing it
                if event.type == InteractionType.component:
                    interaction_message = event.message
                else:
                    # don't think this way would work for other nodes. no response and only thing that has a message attached is a component interaction
                    try:
                        interaction_message = await event.original_response()
                        discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name provided fetched original message")
                    except Exception as e:
                        # there's nothing to edit for interaction response. try to see if regular works
                        if correction_attempts > 0:
                            correction_attempts -= 1
                            settings["correction_attempts"] = correction_attempts
                            settings["respond_interaction"] = False
                            data.base_parameter = settings
                            return await edit_message(data)
                interaction_message_menu_name = active_node.get_menu_name_of(interaction_message.id)
                if interaction_message_menu_name is None or interaction_message_menu_name != menu_name:
                    discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name either not tracked or isn't the interaction message")
                    if correction_attempts > 0:
                        # either interaction message not tracked, or does not match desired menu. go to top of method to try again
                        # with regular route
                        settings["respond_interaction"] = False
                        correction_attempts -= 1
                        settings["correction_attempts"] = correction_attempts
                        data.base_parameter = settings
                        return await edit_message(data)
                else:
                    # interaction response is the menu trying to edit can do response
                    discord_logger.debug(f"found interaction want to respond to and it doesn't have a response and menu name provided can be edited")
                    edit_settings = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
                    if "ping_with_reply" in settings:
                        edit_settings.update({"allowed_mentions": discord.AllowedMentions(replied_user=settings["ping_with_reply"])})
                    await edit_helper(edit_settings, active_node.get_menu_info(menu_name), interaction_mode=True)
    else:
        # any other case of not responding to interaction, or is not an interaction and don't care about this setting, just edit message
        if "menu_name" not in settings:
            # iteraction edit might not care about menu name but this one does so just in case
            discord_logger.warning(f"trying to edit menu but none specified")
            return
        if settings["menu_name"] not in active_node.menu_messages_info:
            discord_logger.debug(f"edit message found menu name listed and not recorded, going to send instead")
            # means this menu message hasn't been sent before, can't do edit, do the send message callback, it will assume destination is same channel
            if correction_attempts > 0:
                correction_attempts -= 1
                settings["correction_attempts"] = correction_attempts
                data.base_parameter = settings
                return await send_message(data)

        edit_settings = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
        if "ping_with_reply" in settings:
            edit_settings.update({"allowed_mentions": discord.AllowedMentions(replied_user=settings["ping_with_reply"])})

        message_info = active_node.menu_messages_info.get(settings["menu_name"], None)
        await edit_helper(edit_settings=edit_settings, message_info=message_info)
        discord_logger.debug(f"finished")
cbUtils.set_callback_settings(edit_message, schema="Schemas/editMessage.yml", runtime_input_key="next_message_settings", allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], reference_schemas=DISCORD_MESSAGE_SCHEMA_PACK)

def setup_next_message(data:cbUtils.CallbackDatapack):
    settings = data.base_parameter
    if "next_message_settings" in data.section_data:
        # if there already are settings, then merge what we want to input into that
        next_message_settings = data.section_data["next_message_settings"]
    else:
        # no settings so can just set up new
        next_message_settings = {}
    merge_message_settings(next_message_settings, settings)
    data.section_data["next_message_settings"] = next_message_settings
    discord_logger.debug(f"set up next message settings, stored in section data. {data.section_data.keys()}")
cbUtils.set_callback_settings(setup_next_message, schema="Schemas/sendMessage.yml", allowed_purposes=[POSSIBLE_PURPOSES.ACTION], reference_schemas=DISCORD_MESSAGE_SCHEMA_PACK)

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION], schema={
    "oneOf":[
        {
            "type":"object", "properties":{
                "channel_id": {"type":"string", "pattern": "((dm:|pm:)?[0-9]{17,19}|(dm:|pm:))"},
                "targets": {"onfOf":[
                    {"type": "string", "enum": ["current_session", "current_node"]}, 
                    {"type":"array", "items": {"type": "string", "enum": ["current_session", "current_node"]}}
                ]}
            }
        },
        {"type":"null"}
    ]
    })
def mark_default_channel(data:cbUtils.CallbackDatapack):
    '''adds to node and/or session a channel id that can be used as default location to send messages to. gets channel id either from yaml `channel_id`
    or from the last message sent in the action section this is used in'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    settings = data.base_parameter

    discord_logger.debug(f"default channel starting")

    if settings is None or "targets" not in settings or settings["targets"] is None:
        targets = ["current_node"]
    elif isinstance(settings["targets"], str):
        targets = [settings["targets"]]
    else:
        targets = settings["targets"]
    
    if settings is not None and "channel_id" in settings:
        channel_id = settings["channel_id"]
    elif "previous_message" in data.section_data:
        channel_id = data.section_data["previous_message"].message.channel.id
    else:
        raise Exception("call to function handling Discord interactions 'mark_default_channel' could not complete")

    if "current_session" in targets and active_node.session is not None:
        active_node.session.data["default_channel"] = channel_id
    if "current_node" in targets:
        discord_logger.debug(f"default channel of {channel_id} marked for node <{id(active_node)}><{active_node.graph_node.id}>")
        setattr(active_node, "default_channel", channel_id)
    
async def clear_buttons(data:cbUtils.CallbackDatapack):
    '''callback or transition callback function clears all interactable components from message and if there are suboptions for it, changes the Discord message's contents
    to the provided messages (to help show oh no we're closed now)'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    settings = data.base_parameter
    to_close_menus = settings["close_menus"] if "close_menus" in settings else list(active_node.menu_messages_info.keys())
    timed_out_message = settings["timeout"] if settings is not None and "timeout" in settings else None
    closed_message = settings["closed"] if settings is not None and "closed" in settings else None

    if len(active_node.menu_messages_info) == 0:
        return
    for menu_name in to_close_menus:
        menu_message_info = active_node.menu_messages_info[menu_name]
        if menu_message_info.view is not None:
            menu_message_info.view.stop()

        if timed_out_message and event["timed_out"]:
            await menu_message_info.message.edit(content=timed_out_message, view=None)
        elif closed_message:
            await menu_message_info.message.edit(content=closed_message, view=None)
        else:
            await menu_message_info.message.edit(view=None)
cbUtils.set_callback_settings(clear_buttons, allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], schema={
    "oneOf": [{
        "type": "object", "properties":{
            "timeout":{"type":"string"}, 
            "closed":{"type":"string"}, 
            "close_menus":{"type":"array", "items": {"type": "string"}}
            }
        },
        {"type": "null"}
    ]
})

def clicked_this_menu(data:cbUtils.CallbackDatapack):
    '''filter function that checks if event (should be an interaction) interacted on one of this node's menus'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    filter_menus = data.base_parameter if data.base_parameter is not None else list(active_node.menu_messages_info.keys())

    if len(active_node.menu_messages_info) == 0:
        return False

    # check every menu in message to see if it is one we care about and it's the message interacted on
    for menu_name, menu_message_info in active_node.menu_messages_info.items():
        if menu_name in filter_menus and menu_message_info.message.id == event.message.id:
            return True
    return False
cbUtils.set_callback_settings(clicked_this_menu, allowed_purposes=[POSSIBLE_PURPOSES.FILTER], schema = {
    "oneOf": [
        {
        "type": "array",
        "items": {"type": "string"}
        },
        {"type": "null"}
    ]
})

async def remove_message(data:cbUtils.CallbackDatapack):
    '''callback function that deletes all discord messages recorded as menu or secondary in node. secondary should be supplementary messages sent by bot'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    settings = data.base_parameter

    if settings is None:
        settings = [ALL_MENUS_KEY, ALL_REPLIES_KEY]
    elif isinstance(settings, str):
        settings = [settings]

    if ALL_MENUS_KEY in settings:
        await active_node.close_all_menus()
    else:
        for menu_name in settings:
            await active_node.delete_menu_message(menu_name)

    if ALL_REPLIES_KEY in settings:
        try:
            await active_node.delete_all_replies()
        except discord.Forbidden as e:
            pass
cbUtils.set_callback_settings(remove_message, allowed_purposes=[POSSIBLE_PURPOSES.ACTION], schema={"oneOf":[
    {"type":"null"}, {"type":"string"}, {"type":"array", "items":{"type":"string"}}]})

def button_is(data:cbUtils.CallbackDatapack):
    '''filter or transition function checks if button event is one of allowed ones passed in custom_ids'''
    func_override_key = "button_is_override"
    custom_ids = copy.deepcopy(data.base_parameter)
    if func_override_key in data.section_data:
        custom_ids = data.section_data.get(func_override_key, [])
        del data.section_data[func_override_key]

    event = data.event
    if isinstance(custom_ids, str):
        return event.data["custom_id"] == custom_ids
    elif isinstance(custom_ids, list):
        return event.data["custom_id"] in custom_ids
    else:
        return False
cbUtils.set_callback_settings(button_is, runtime_input_key="button_is_override", allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.FILTER], schema={
    "oneOf":[
        {"type":"null"},
        {"type":["string", "integer"]},
        {"type":"array", "items":{"type":["string", "integer"]}}
    ]
})

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.FILTER], runtime_input_key="is_allowed_user_override", schema={
    "onfOf":[
        {"type": "string", "enum": [a.value for a in NodetionBaseFuncs.NODES_AND_SESSION]}, 
        {"type":"array", "items": {"type": "string", "enum": [a .value for a in NodetionBaseFuncs.NODES_AND_SESSION]}}
    ]
})
def is_allowed_user(data:cbUtils.CallbackDatapack):
    '''filter or transition filter function that checks if the user for the interaction or message event is the same one as what is recorded in the
    ndoe's session.'''
    discord_logger.info(f"is_allowed_user starting execution")
    func_override_key = "is_allowed_user_override"
    targets = copy.deepcopy(data.base_parameter)
    if func_override_key in data.section_data:
        targets = data.section_data.get(func_override_key, [])
        del data.section_data[func_override_key]

    if isinstance(targets, str):
        targets = [targets]
    elif targets is None:
        return False
    discord_logger.debug(f"final targets to check is {targets}")

    event = data.event
    if isinstance(event, Interaction):
        user = event.user
    elif isinstance(event, discord.Message):
        user = event.author
    elif isinstance(event, Context):
        user = event.author
    else:
        raise Exception(f"wrong event types called is_allowed_user. got {event}, expected discord interaction or message")

    allowed_set = set()
    for target in targets:
        discord_logger.debug(f"checking allowed users, combining allowed from {target}")
        allowed_user_list = NodetionBaseFuncs.get_data(data, target + ".allowed_users", default=[])
        for user_id in allowed_user_list:
            allowed_set.add(user_id)

    discord_logger.debug(f"is allowed finished checks, result {user.id in allowed_set}")
    return user.id in allowed_set

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_ACTION, POSSIBLE_PURPOSES.ACTION], runtime_input_key="mark_allowed_user_override", schema={
    "onfOf":[
        {"type": "string", "enum": [a.value for a in NodetionBaseFuncs.NODES_AND_SESSION]}, 
        {"type":"array", "items": {"type": "string", "enum": [a.value for a in NodetionBaseFuncs.NODES_AND_SESSION]}}
    ]
})
def mark_allowed_user(data:cbUtils.CallbackDatapack):
    '''transition callback function that records the user that triggered the interaction or message event as the owner of the session'''
    discord_logger.info("mark_allowed_user started execution")
    func_override_key = "mark_allowed_user_override"
    targets = copy.deepcopy(data.base_parameter)
    if func_override_key in data.section_data:
        targets = data.section_data.get(func_override_key, None)
        del data.section_data[func_override_key]
    
    if targets is None:
        return
    elif isinstance(targets, str):
        targets = [targets]

    event = data.event
    if isinstance(event, Interaction):
        user = event.user
    elif isinstance(event, discord.Message):
        user = event.author
    elif isinstance(event, Context):
        user = event.author
    else:
        raise Exception(f"wrong event types called mark_allowed_user. got {event}, expected discord interaction or message")

    for save_location in targets:
        location = NodetionBaseFuncs.get_data(data, save_location, None)
        if location is None:
            continue
        user_list = NodetionBaseFuncs.get_data(data, save_location+".allowed_users", None)
        if user_list is None:
            NodetionBaseFuncs.handle_save_ref(set(), save_location+".allowed_users", data)
            user_list = NodetionBaseFuncs.get_data(data, save_location+".allowed_users", None)
        user_list.add(user.id)

@cbUtils.callback_settings(runtime_input_key="is_reply_override", allowed_purposes=[POSSIBLE_PURPOSES.FILTER], schema={
    "oneOf": [
        {
            "type":"array", 
            "items":{"oneOf": [
                {"type": "string"},
                {"type": "integer"}
            ]}
        },
        {"type": "null"}
    ]
})
def is_reply(data:cbUtils.CallbackDatapack):
    '''filter function that checks if message event is replying to menu message, with settings to check if it is a reply to secondary or reply messages'''
    func_override_key = "is_reply_override"
    settings = copy.deepcopy(data.base_parameter)
    # settings is None or list
    if func_override_key in data.section_data:
        if data.section_data.get(func_override_key, None) is not None:
            # if there is something to override with, do so
            settings = data.section_data.get(func_override_key, [])
        del data.section_data[func_override_key]
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event

    if not hasattr(event, "reference") or event.reference is None:
        return False
    if settings is None:
        # assume meant as reply to any message tracked by this node is ok. can be done by checking if replied to message id is tracked by node
        return active_node.check_tracking(event.reference.message_id) is not None
    else:
        # assume settings define a subset of messages that are what we want to check if is a reply to
        to_check_message_ids = set()
        for item in settings:
            # passed in can be menu names, message ids, or keywords
            # assuming that menu names and keywords always strings and message ids might be string or int
            if isinstance(item, str):
                if item == ALL_MENUS_KEY:
                    for message_info in active_node.menu_messages_info.values():
                        to_check_message_ids.add(message_info.message.id)
                elif item == ALL_REPLIES_KEY:
                    for message_info in active_node.managed_replies_info:
                        to_check_message_ids.add(message_info.message.id)
                elif item in active_node.menu_messages_info:
                    # string name for a menu
                    message_info = active_node.menu_messages_info[item]
                    to_check_message_ids.add(message_info.message.id)
                else:
                    # in case message id saved as string
                    try:
                        num = int(item)
                        to_check_message_ids.add(num)
                    except Exception as e:
                        pass
            else:
                # is a number. assume message id
                to_check_message_ids.add(item)

        return event.reference.message_id in to_check_message_ids
    
@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_ACTION], schema={
    "onfOf":[{"type":"null"}, {"type": "string"}, {"type":"array", "items": {"type": "string"}}]})
def transfer_menus(data:cbUtils.CallbackDatapack):
    '''transition action that moves the menu message from this node to the next node so the next node can edit the message instead of
    sending a new one'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    goal_node:DiscordNodeType.DiscordNode = data.goal_node
    settings = data.base_parameter
    
    if isinstance(settings , str):
        settings = [settings]
    if settings is None:
        settings = list(active_node.menu_messages_info.keys())
    
    # settings is list of strings for next part    
    for menu_name in settings:
        if menu_name in active_node.menu_messages_info:
            goal_node.record_menu_message(menu_name, active_node.menu_messages_info[menu_name])
            del active_node.menu_messages_info[menu_name]

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key='rename_menu_override', schema={
    "type":"object", "properties":{
        "target": {"type":"string", "enum": [a.value for a in NodetionBaseFuncs.NODES]},
        "from":{"type": "string"},
        "to":{"type": "string"}
        }, "required":["target","from","to"]
})
def rename_menu(data:cbUtils.CallbackDatapack):
    '''transition action that moves the menu message from this node to the next node so the next node can edit the message instead of
    sending a new one'''
    settings = NodetionBaseFuncs.default_handle_run_input("rename_menu_override", data)
    
    active_node:DiscordNodeType.DiscordNode = data.active_node
    goal_node:DiscordNodeType.DiscordNode = data.goal_node
    
    if settings["target"] == NodetionBaseFuncs.YAML_SELECTION.ACTIVE_NODE.value:
        node = active_node
    else:
        node = goal_node
    
    if settings["to"] in node.menu_messages_info:
        discord_logger.warning(f"name provided that want to rename to already being used. not doing it")
        return None
    if settings["from"] not in node.menu_messages_info:
        discord_logger.warning(f"name provided to rename from not in node. not doing it")
        return None
    node.menu_messages_info[settings["to"]] = node.menu_messages_info[settings["from"]]
    del node.menu_messages_info[settings["from"]]

@cbUtils.callback_settings(runtime_input_key="selection_is_override", allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], schema={"type":"object",
    "properties":{
        "custom_id":{"type":"string"},
        "selection":{"oneOf":[
            {"type":"string"},
            {"type": "array", "items": {"type":"string"}},
            {"type": "array", "items": {"type": "array", "items": {"type":"string"}}}]}
    }, "required":["custom_id", "selection"]
})
def selection_is(data:cbUtils.CallbackDatapack):
    '''filter or transition filter function that checks if the selection menu interaction is choosing a specific value'''
    # single string, selection has max of one
    # array is one single group with multiple options selected
    # array of groups requires each group has array type to differentiate this from single group
    func_override_key = "selection_is_override"
    settings = NodetionBaseFuncs.default_handle_run_input("selection_is_override", data)

    event = data.event

    # event has to be an interaction, and select component interaction
    if not isinstance(event, Interaction) or \
            not event.type == InteractionType.component or \
            not event.data["component_type"] == discord.ComponentType.select.value:
        return False
    # event has to be on selected custom id
    if event.data["custom_id"] != settings["custom_id"]:
        return False

    discord_logger.info(f"selection is starting with passed in settings {settings['selection']}")
    if isinstance(settings["selection"], str):
        # is just one setting, assuming single acceptable combination with only one selectable option
        settings["selection"] = [[settings["selection"]]]
    if isinstance(settings["selection"], list):
        # can either be one combination or a list of multiple combinations
        if len(settings["selection"]) == 0:
            # invalid structure
            return False
        if isinstance(settings["selection"][0], str):
            # means one combination
            settings["selection"] = [settings["selection"]]
    discord_logger.info(f"selection is massaged input, {settings['selection']}")
    discord_logger.info(f"selection is event selection is, {event.data['values']}")

    event.data["values"].sort()
    for combination in settings["selection"]:
        combination.sort()
        if combination == event.data["values"]:
            discord_logger.info(f"found combination that matches event: {combination}")
            return True
    return False

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], schema={
    "oneOf": [
        {
            "type":["string","integer"]
        },
        { "type":"null"}
    ]
})
def is_server_member(data:cbUtils.CallbackDatapack):
    active_node = data.active_node
    event = data.event
    goal_node = data.goal_node
    server_id = data.base_parameter

    if (active_node.session is None or "server_id" not in active_node.session.data or active_node.session.data["server_id"] is None) and server_id is None:
        return False

    if server_id is None:
        # in order to get in this if, there needs to be a server id in session
        server_id = active_node.session.data["server_id"]

    bot = data.bot
    server = bot.get_guild(server_id)
    if server is None:
        return False

    if isinstance(event, Interaction):
        user = event.user
    else:
        user = event.author
    return server.get_member(user.id) is None

def is_in_DM(data:cbUtils.CallbackDatapack):
    event = data.event
    # this works for Discord Message, Context, or Interaction
    return event.channel.type == discord.ChannelType.private
cbUtils.set_callback_settings(is_in_DM, allowed_purposes=[POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER], description_blurb="checks if event happened in dm")

dialog_func_info = {send_message:{}, clear_buttons:{}, setup_next_message:{},
                    clicked_this_menu:{}, button_is:{}, remove_message:{},
                    is_allowed_user:{}, mark_allowed_user:{},
                    is_reply:{}, selection_is:{}, edit_message:{},
                    transfer_menus:{}, is_server_member:{}, mark_default_channel:{}, rename_menu:{},
                    is_in_DM:{}}