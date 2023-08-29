import discord
from discord import ui
import copy

class MessageInfo:
    def __init__(self, message, view=None) -> None:
        self.message = message
        self.view = view
        self.deleted = False

def build_button(button_settings):
    '''builds a discord ui button component from settings listed in a dictionary'''
    filtered_settings = {}
    for setting in ["custom_id", "label", "disabled", "url", "emoji", "row"]:
        if setting in button_settings:
            filtered_settings[setting] = button_settings[setting]

    if "style" in button_settings:
        filtered_settings["style"] = discord.ButtonStyle[button_settings["style"]]
    return ui.Button(**filtered_settings)

def build_select_menu(component_settings):
    '''builds a discord select ui component from settings listed in a nested dictionary'''
    filtered_settings = {}
    for v in ["custom_id", "placeholder", "min_values", "max_values", "disabled", "row"]:
        if v in component_settings:
            filtered_settings[v] = component_settings[v]
    
    select_comp = ui.Select(**filtered_settings)

    for option in component_settings["options"]:
        option_settings = {}
        for v in ["label", "value", "description", "emoji", "default"]:
            if v in option:
                option_settings[v] = option[v]
        select_comp.add_option(**option_settings)
    return select_comp


def build_discord_message(message_settings, TTL, default_fills={}):
    ''' converts yaml settings to a dictionary for discord message constructor with all views and embeds etc components initialized'''
    #NOTE: don't forget that default values are evaluated once, and mutable objects will be the same object every call
    to_send_bits = copy.deepcopy(default_fills)
    if "components" in message_settings and message_settings["components"] is not None and len(message_settings["components"]) > 0:
        view = ui.View(timeout=TTL)
        for component in message_settings["components"]:
            if component["type"] == "Button":
                view.add_item(build_button(component))

            elif component["type"] == "SelectMenu":
                view.add_item(build_select_menu(component))

        to_send_bits["view"] = view

    if "content" in message_settings and message_settings["content"] is not None:
        to_send_bits["content"] = message_settings["content"]
    
    if "embed" in message_settings and message_settings["embed"] is not None:
        embed = discord.Embed()
        for field in message_settings["embed"]["fields"]:
            embed.add_field(**field)
    return to_send_bits

def build_discord_modal():
    #TODO
    pass

def record_sent_message(active_node, msg_info, is_menu=False):
    if not hasattr(active_node, "secondary_messages"):
        active_node.secondary_messages = set()
    if is_menu:
        # if haven't recorded focal, assuming first send response is going to be focal ie is the message doing the most important interaction and chaining stuff
        active_node.menu_message = msg_info
        # print(f"active node id'd <{id(active_node)}> set message snowflake id'd <{id(msg_info.message.id)}> <{msg_info.message.content}> to menu message")
    else:
        active_node.secondary_messages.add(msg_info)
        # print(f"active node id'd <{id(active_node)}> added message snowflake id'd <{id(msg_info.message.id)}> <{msg_info.message.content}> to secondary messages")
    if not hasattr(active_node, "menu_message"):
        active_node.menu_message = None
    if not hasattr(active_node, "managed_replies"):
        active_node.managed_replies = set()

def record_reply(active_node, msg_info):
    if not hasattr(active_node, "managed_replies"):
        active_node.managed_replies = set()
    active_node.managed_replies.add(msg_info)