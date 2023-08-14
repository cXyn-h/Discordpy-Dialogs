import discord
from discord import ui
class MessageInfo:
    def __init__(self, message, view=None) -> None:
        self.message = message
        self.view = view
        self.deleted = False

def build_button(component):
    button_comp_settings = {}
    for v in ["custom_id","label", "disabled","url","emoji","row"]:
        if v in component:
            button_comp_settings[v] = component[v]

    if "style" in component:
        button_comp_settings["style"] = discord.ButtonStyle[component["style"]]
    return ui.Button(**button_comp_settings)

def build_select_menu(component):
    select_comp_settings = {}
    for v in ["custom_id", "placeholder", "min_values", "max_values", "disabled", "row"]:
        if v in component:
            select_comp_settings[v] = component[v]
    
    select_comp = ui.Select(**select_comp_settings)

    for option in component["options"]:
        option_settings = {}
        for v in ["label", "value", "description", "emoji", "default"]:
            if v in option:
                option_settings[v] = option[v]
        select_comp.add_option(**option_settings)
    return select_comp


def build_discord_message(message_settings, TTL):
    ''' converts yaml settings to a dictionary for discord message constructor with all views and embeds etc components initialized'''
    to_send_bits = {}
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

def buidl_discord_modal():
    #TODO
    pass

def record_sent_message(active_node, msg_info):
    if not hasattr(active_node, "secondary_messages"):
        active_node.secondary_messages = set()
    if not hasattr(active_node, "focal_message") or active_node.focal_message is None:
        # if haven't recorded focal, assuming first send response is going to be focal ie is the message doing the most important interaction and chaining stuff
        active_node.focal_message = msg_info
    else:
        active_node.secondary_messages.add(msg_info)
    if not hasattr(active_node, "managed_replies"):
        active_node.managed_replies = set()