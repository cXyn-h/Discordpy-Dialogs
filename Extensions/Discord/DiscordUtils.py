import discord
from discord import ui
import copy

class NodetionDCMenuInfo:
    def __init__(self, message, view=None) -> None:
        self.message:discord.Message = message
        self.view:ui.View = view
        self.deleted = False
        # Nodetion itself tracking this to avoid some potential errors from trying to delete message that has already been deleted
        self.page = None
        # page is not in default discord message. This is tracking from
        # Nodetion itself for data that can't fit in a single discord message.

    def serialize(self):
        return {"message_id": self.message.id, "has_view": self.view != None, "deleted": self.deleted, "page": self.page}

def check_components_fit(components_settings, extras=None):
    extras = extras if extras is not None else {}
    layout = [0,0,0,0,0]
    latest_position = 0

    max_row_score = 5
    for component_list in [components_settings, extras]:
        for component in component_list:
            if component["type"] == "Button":
                if "row" in component:
                    layout[component["row"]] += 1
                else:
                    layout[latest_position] += 1
                    if layout[latest_position] >= max_row_score:
                        latest_position += 1
            elif component["type"] == "SelectMenu":
                if "row" in component:
                    layout[component["row"]] += max_row_score
                else:
                    layout[latest_position] += max_row_score
                    if layout[latest_position] >= max_row_score:
                        latest_position += 1
            if len([x for x in layout if x > max_row_score]) > 1:
                return False
    return True

def build_discord_button(button_settings):
    '''builds a discord ui button component from settings listed in a dictionary'''
    filtered_settings = {}
    for setting in ["custom_id", "label", "disabled", "url", "emoji", "row"]:
        if setting in button_settings:
            filtered_settings[setting] = button_settings[setting]

    if "style" in button_settings:
        filtered_settings["style"] = discord.ButtonStyle[button_settings["style"]]
    return ui.Button(**filtered_settings)

def build_discord_select_menu(component_settings):
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

def build_discord_embed(embed_settings):
    #TODO: timestamp support from yaml?
    #TODO: embed has author and some other fields
    #TODO: there's embed types
    filtered_settings = {}
    for v in ["title", "type", "description", "url"]:
        if v in embed_settings:
            filtered_settings[v] = embed_settings[v]
    if "colour" in embed_settings:
        if isinstance(embed_settings["colour"], str):
            filtered_settings["colour"] = getattr(discord.Colour, embed_settings["colour"])
        if isinstance(embed_settings["colour"], int):
            filtered_settings["colour"] = discord.Colour(embed_settings["colour"])
    embed = discord.Embed(**filtered_settings)

    if "footer" in embed_settings:
        filtered_footer_settings = {}
        for v in ["text", "icon_url"]:
            if v in embed_settings["footer"]:
                filtered_footer_settings[v] = embed_settings["footer"][v]
        embed.set_footer(**filtered_footer_settings)

    for field in embed_settings["fields"]:
        embed.add_field(**field)
    return embed

def build_discord_components(components_settings):
    # planned is nodes will have to manage view, not leaving it to discord default behaviors cause of issues with getting
    # button events straight during early development of this project
    view = ui.View(timeout=None)
    for component in components_settings:
        if component["type"] == "Button":
            view.add_item(build_discord_button(component))

        elif component["type"] == "SelectMenu":
            view.add_item(build_discord_select_menu(component))
    return view

def build_discord_message(message_settings, default_fills:dict=None):
    '''converts yaml settings to a dictionary that can be passed to Discord `message` constructor with all views and embeds etc components initialized.
    default fills are values to use if yaml settings do not specify values for fields. this function does not copy it so be careful reusing the same dict for multiple calls'''
    #NOTE: don't forget that default values are evaluated once, and mutable objects will be the same object every call
    to_send_bits = default_fills if default_fills is not None else {}
    if "components" in message_settings and message_settings["components"] is not None and len(message_settings["components"]) > 0:
        # timeout for view works differently from timeout for nodes, nodes will have to manage view
        to_send_bits["view"] = build_discord_components(message_settings["components"])

    if "content" in message_settings and message_settings["content"] is not None:
        to_send_bits["content"] = message_settings["content"]
    
    if "embeds" in message_settings and message_settings["embeds"] is not None:
        to_send_bits["embeds"] = [build_discord_embed(embed) for embed in message_settings["embeds"]]

    return to_send_bits

def build_discord_modal():
    #TODO build modal
    pass