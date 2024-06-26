import discord
from discord import InteractionType
from discord.ext.commands import Bot

import src.DialogHandler as DialogHandler
# callbacks that provide extended functionality
import Examples.Discord.DiscordMessagingFuncs as DiscordBaseFuncs
import Examples.Discord.SpecificTestingFuncs as SpecializedFuncs
import Examples.Discord.DiscordEvents as DiscordEvents
import logging

logger = logging.getLogger('discord')

class SimpleBot(Bot):
    def __init__(self, **kargs):
        super().__init__(**kargs)
        self.loaded = False
        self.main_menu_handler = DialogHandler.DialogHandler(bot=self)
        self.main_menu_handler.setup_from_files(["Examples/Discord/WalkthroughMenu.yaml"])
        self.main_menu_handler.register_module(DiscordBaseFuncs)
        self.main_menu_handler.register_module(SpecializedFuncs)
        self.main_menu_handler.final_validate()
        # can instantiate more handlers to manage separate areas

    async def on_ready(self):
        if self.loaded:
            logger.info('reconnected as {0.user}'.format(self))
        else:
            logger.info('We have logged in as {0.user}'.format(self))
            self.loaded = True
            self.main_menu_handler.start_cleaning(self.loop)

        
    async def on_interaction(self, interaction):
        # NOTE: discord.py comes with views to handle interaction components on messages, but we're overriding those and handling it ourselves
        #       because during designing there was a bug where different view objects with components with same name would get confused.
        print(f"bot on interaction entry point, interaction is <{interaction}>, type is <{interaction.type}> data is <{interaction.data}> response done? <{interaction.response.is_done()}>")
        
        if interaction.type == InteractionType.component:
            if interaction.data["component_type"] == discord.ComponentType.button.value:
                await self.main_menu_handler.handle_event("button_click", interaction)
            if interaction.data["component_type"] == discord.ComponentType.select.value:
                await self.main_menu_handler.handle_event("select_menu", interaction)
        elif interaction.type == InteractionType.application_command:
            await self.main_menu_handler.handle_event("application_command", interaction)
        elif interaction.type == InteractionType.modal_submit:
            await self.main_menu_handler.handle_event("modal_submit", interaction)