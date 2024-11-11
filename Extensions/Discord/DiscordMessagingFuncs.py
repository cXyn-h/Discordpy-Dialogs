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
from src.utils.Enums import POSSIBLE_PURPOSES

import logging
import src.utils.LoggingHelper as logHelper
discord_logger = logging.getLogger('Discord Callbacks')
logHelper.use_default_setup(discord_logger)
discord_logger.setLevel(logging.INFO)

ALL_MENUS_KEY = "*all_menus"
ALL_REPLIES_KEY = "*all_replies"

def merge_message_settings(base, addon):
    '''takes two sets of messages and their sending options and moves settings in addon into base. Overwrites simple types, adds on to lists'''
    for setting in ["menu_name", "dest_channel_id", "ping_with_reply"]:
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

#TODO: add checks to make sure there is a valid set of data after combining message settings from yaml and overrides
async def send_message(data:cbUtils.CallbackDatapack):
    '''callback function that sends a discord message with provided settings.'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    bot = data.bot

    # override yaml with anything that is generated in function_data
    runtime_input_key = "next_message_settings"
    settings = data.base_parameter
    if runtime_input_key in data.section_data:
        settings = merge_message_settings(data.base_parameter if data.base_parameter is not None else {}, data.section_data[runtime_input_key])
        del data.section_data[runtime_input_key]
    
    discord_logger.debug(f"send message settings chosen are <{settings}>")

    if settings["menu_name"] in active_node.menu_messages_info:
        discord_logger.debug(f"send message going to edit message instead for menu <{settings['menu_name']}>")
        # found there's already a menu being tracked under given name, need to handle existing tracking, edit should already know how
        data.base_parameter = settings
        return await edit_message(data)

    message_components = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
    # find out which channel message supposed to be sent to as that affects how we are replying to interaction
    # let function callbacks that already found channel object override by passing in dest_channel key, otherwise need to read id and try to fetch channel
    try:
        if "dest_channel" in settings:
            dest_channel = settings["dest_channel"]
            discord_logger.debug(f"dest channel was overridden in settings <{dest_channel}>")
        elif "dest_channel_id" in settings:
            discord_logger.debug(f"dest channel is id. searching given value <{settings['dest_channel_id']}>")
            # either just a prefix "dm:" or "pm:", prefix and then user id, or no prefix and is channel id (dm or otherwise)
            if isinstance(settings["dest_channel_id"], str) and settings["dest_channel_id"].find(":") > -1:
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
        elif active_node.session is not None and "default_channel" in active_node.session.data:
            dest_channel = bot.get_channel(int(active_node.session.data["default_channel"]))
        elif hasattr(active_node, "default_channel"):
            discord_logger.debug(f"default channel on node found, {getattr(active_node, 'default_channel')}")
            dest_channel = bot.get_channel(int(getattr(active_node, "default_channel")))
        else:
            discord_logger.debug(f"sanity check vars of active node {vars(active_node)}")
            dest_channel = event.channel
            discord_logger.debug(f"no dest channel. defaulting to channel event is from <{dest_channel}>")
        if dest_channel is None:
                discord_logger.debug(f"send message early found that dest channel is invalid")
                # invalid id or other issue fetching channel object
                return
    except Exception as e:
        discord_logger.error(f"SOMETHING REALLY BAD IN SEND MESSAGE {e}")
    dest_is_dm = dest_channel.type == discord.ChannelType.private

    discord_logger.debug(f"send message found intended dest channel, continuing")
    if isinstance(event, Interaction) and not event.response.is_done():
        discord_logger.debug(f"send message found interaction not responded to")
        # if interaction, want to try replying to event as much as possible.
        # if event already handled, try sending regular way
        #TODO: ephemeral message support? might mess with storing message in node data?
        #TODO: could add ping_with_reply checking on replying to interaction part
        if event.channel.id == dest_channel.id:
            discord_logger.debug(f"send message interaction happened in same channel, can send reply")
            # message meant to be sent in channel event originated from, safe to send as response
            dirty = False
            if message_components["view"] is None:
                del message_components["view"]
                dirty = True
            # interaction send_message doesn't like view being null, but message info uses null to mean no view, so remove briefly for send message
            await event.response.send_message(**message_components)
            if dirty:
                message_components["view"] = None
            sent_message = await event.original_response()
            discord_logger.debug(f"interaction sent response is <{sent_message.id}>, {sent_message}")
            sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
            active_node.record_menu_message(settings["menu_name"], sent_message_info)
            data.section_data["previous_message"] = sent_message_info
        else:
            discord_logger.debug(f"send message interaction didn't happen in destination channel")
            # event channel is different from intended destination
            if "redirect_message" in settings:
                discord_logger.debug(f"different destination there's a redirect to send")
                # settings on a message to draw attention to content has been sent somewhere else
                redirect_message = DiscordUtils.build_discord_message(settings["redirect_message"])
                await event.response.send_message(**redirect_message)
                sent_message = await event.original_response()
                if "view" not in redirect_message:
                    # interaction send_message doesn't like view is None, but using none types in message info for nothing there
                    redirect_message["view"] = None
                discord_logger.debug(f"interaction replied with redirect message, the message is <{sent_message.id}>, <{sent_message}>")
                active_node.record_menu_message(settings["menu_name"]+"_redirect", DiscordUtils.NodetionDCMenuInfo(sent_message, redirect_message["view"]))
            sent_message = await dest_channel.send(**message_components)
            discord_logger.debug(f"sent actual message to correct destination channel, the message is <{sent_message.id}>, <{sent_message}>")
            sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
            active_node.record_menu_message(settings["menu_name"], sent_message_info)
            data.section_data["previous_message"] = sent_message_info
    else:
        discord_logger.debug(f"send message either interaction already responded or non-interaction response")
        # either non-interaction event or interaction already handled
        # take message and send to given dest
        if isinstance(event, discord.Message):
            reference_message = event
        elif isinstance(event, Interaction) or isinstance(event, Context):
            # interaction or message command context
            reference_message = event.message
        else:
            discord_logger.warning(f"send message not given valid event type to get user for dm channel cause not specified in settings")
            return None
        if event.channel.id == dest_channel.id:
            discord_logger.debug(f"send message can respond in same channel")
            if "ping_with_reply" in settings:
                discord_logger.debug(f"need to reply to message")
                sent_message = await event.channel.send(**message_components, allowed_mentions=discord.AllowedMentions(replied_user=settings["ping_with_reply"]), reference=reference_message)
            else:
                discord_logger.debug(f"no reply setting so regular send")
                sent_message = await event.channel.send(**message_components)
            discord_logger.debug(f"sent message is <{sent_message.id}>, <{sent_message}>")
            sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
            active_node.record_menu_message(settings["menu_name"], sent_message_info)
            data.section_data["previous_message"] = sent_message_info
        else:
            discord_logger.debug(f"send message non-interaction response is not in destination channel")
            # event channel is different from intended destination
            if "redirect_message" in settings:
                discord_logger.debug(f"there's a redirect message")
                # settings on a message to draw attention to content has been sent somewhere else
                redirect_message = DiscordUtils.build_discord_message(settings["redirect_message"], default_fills={"view":None})
                if "ping_with_reply" in settings:
                    discord_logger.debug(f"need to reply using redirect")
                    sent_message = await event.channel.send(**redirect_message, allowed_mentions=discord.AllowedMentions(replied_user=settings["ping_with_reply"]), reference=reference_message)
                else:
                    discord_logger.debug(f"no reply setting")
                    sent_message = await event.channel.send(**redirect_message)
                discord_logger.debug(f"sent redirect is <{sent_message.id}>, <{sent_message}>")
                active_node.record_menu_message(settings["menu_name"]+"_redirect", DiscordUtils.NodetionDCMenuInfo(sent_message, redirect_message["view"]))
            sent_message = await dest_channel.send(**message_components)
            discord_logger.debug(f"sent message is <{sent_message.id}>, <{sent_message}>")
            sent_message_info = DiscordUtils.NodetionDCMenuInfo(sent_message, message_components["view"])
            active_node.record_menu_message(settings["menu_name"], sent_message_info)
            #TODO: TEST out this with timeout event now being able to grab and save data
            data.section_data["previous_message"] = sent_message_info     
cbUtils.set_callback_settings(send_message, schema="FuncSchemas/sendMessageSchema.yml", runtime_input_key="next_message_settings", allowed_purposes=[POSSIBLE_PURPOSES.ACTION])

async def edit_message(data:cbUtils.CallbackDatapack):
    '''callback that edits the menu specified or previous message'''
    active_node:DiscordNodeType.DiscordNode = data.active_node
    event = data.event
    bot = data.bot

    settings = data.base_parameter
    if "next_message_settings" in data.section_data:
        settings = merge_message_settings(data.base_parameter if data.base_parameter is not None else {}, data.section_data["next_message_settings"])
        del data.section_data["next_message_settings"]

    if "menu_name" in settings and settings["menu_name"] not in active_node.menu_messages_info:
        discord_logger.debug(f"edit message found menu name listed and not recorded, going to send instead")
        # means this menu message hasn't been sent before, can't do edit, do the send message callback, it will assume destination is same channel
        data.base_parameter = settings
        return await send_message(data)

    message_components = DiscordUtils.build_discord_message(settings["message"], default_fills={"view":None})
    made_edits = False

    # if menu name specified, that is what we are editing with message
    #   if interaction want to try edit to fulfill interaction response
    #   otherwise edit message stored in info
    # otherwise editing whatever caused the event
    # if there is a rediret message, send that as well
    if "menu_name" in settings:
        discord_logger.debug(f"edit message menu name specified")
        message_info = active_node.menu_messages_info[settings["menu_name"]]
        if message_info.deleted:
            discord_logger.warning(f"edit message trying to edit menu <{settings['menu_name']}> but target message already deleted. not doing anything else")
            return
        if isinstance(event, Interaction) and not event.response.is_done() and message_info.message.id == event.message.id:
            discord_logger.debug(f"interaction event happened on same message that is targeted, can edit and respond")
            # only do edit response if component interaction happened on targeted menu
            await event.response.edit_message(**message_components)
            edited_message = await event.original_response()
        else:
            discord_logger.debug(f"either not interaction or cannot do interaction response, plain edit")
            discord_logger.info(f"sanity check, message info contnt before edit {active_node.menu_messages_info[settings['menu_name']].message.content}")
            edited_message = await message_info.message.edit(**message_components)
        made_edits = True
        # message object in message info is old, update
        message_info.message = edited_message
        discord_logger.info(f"sanity check, message info content after edit {active_node.menu_messages_info[settings['menu_name']].message.content}")
        if "view" in message_components:
            discord_logger.debug(f"view was specified in message, removing old one")
            # this will most likely be part of message components every call, but leaving in check anyways. need to clean up old view properly
            if message_info.view is not None:
                discord_logger.debug(f"stopping old view")
                message_info.view.stop()
            message_info.view = message_components["view"]
        data.section_data["previous_message"] = message_info
    else:
        discord_logger.debug(f"menu name not specified, so using origin message")
        # menu name not specified, defaults to what caused the event
        if isinstance(event, Interaction):
            discord_logger.debug(f"handling interaction edit")
            target_message = event.message
            if not event.response.is_done():
                discord_logger.debug(f"editing message that caused interaction")
                await event.response.edit_message(**message_components)
                edited_message = await event.original_response()
            else:
                discord_logger.debug(f"interaction response already done, regular edit")
                edited_message = await target_message.edit(**message_components)
            made_edits = True

            # double check if message that was just edited was already tracked
            if active_node.check_tracking(target_message.id) == "menu":
                discord_logger.debug(f"target message is tracked as menu message, refreshing view")
                for menu_name in active_node.menu_messages_info.keys():
                    message_info = active_node.menu_messages_info[menu_name]
                    if message_info.message.id == target_message.id:
                        # found the menu with the message id just edited
                        # getting menu name loaded so redirect has a menu name
                        discord_logger.debug(f"found target message")
                        settings["menu_name"] = menu_name
                        message_info.message = edited_message
                        if "view" in message_components:
                            if message_info.view is not None:
                                message_info.view.stop()
                            message_info.view = message_components["view"]
                        data.section_data["previous_message"] = message_info
                        break
        # no else, usually this would be message or slash command events and there'd be nothing to edit
    discord_logger.debug(f"got to redirect handling, was a message edited? <{made_edits}>")
    if made_edits and "redirect_message" in settings:
        discord_logger.debug(f"redirect message needs to be sent")
        redirect_message = DiscordUtils.build_discord_message(settings["redirect_message"], default_fills={"view": None})
        if isinstance(event, Interaction) and not event.response.is_done():
            # come to think of it this path probably won't be hit if you have to have made an edit to send redirect. because editing will try to 
            # respond to interaction before redirect is sent
            discord_logger.debug(f"redirect message being sent as interaction response")
            dirty = False
            if redirect_message["view"] is None:
                del redirect_message["view"]
                dirty = True
            await event.response.send_message(**redirect_message)
            if dirty:
                # interaction send_message doesn't like view is None, but using none types in message info for nothing there
                redirect_message["view"] = None
            sent_message = await event.original_response()
            active_node.record_menu_message(settings["menu_name"]+"_redirect", DiscordUtils.NodetionDCMenuInfo(sent_message, redirect_message["view"]))
        else:
            if isinstance(event, discord.Message):
                reference_message = event
            else:
                # interaction or message command context
                reference_message = event.message
            discord_logger.debug(f"either interaction already responded or not interaction event, redirect being sent as regular message")
            if "ping_with_reply" in settings:
                sent_message = await event.channel.send(**redirect_message, allowed_mentions=discord.AllowedMentions(replied_user=settings["ping_with_reply"]), reference=reference_message)
            else:
                sent_message = await event.channel.send(**redirect_message)
            active_node.record_menu_message(settings["menu_name"]+"_redirect", DiscordUtils.NodetionDCMenuInfo(sent_message, redirect_message["view"]))
    discord_logger.debug(f"finished")
cbUtils.set_callback_settings(edit_message, schema="FuncSchemas/editMessageSchema.yml", runtime_input_key="next_message_settings", allowed_purposes=[POSSIBLE_PURPOSES.ACTION])

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
cbUtils.set_callback_settings(setup_next_message, schema="FuncSchemas/sendMessageSchema.yml", allowed_purposes=[POSSIBLE_PURPOSES.ACTION])

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
        return active_node.check_tracking(event.reference.message_id) is None
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