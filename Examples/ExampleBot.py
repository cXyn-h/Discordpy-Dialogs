import discord
from discord import InteractionType, Interaction
from discord.ext import commands
from discord.ext.commands import Bot

import src.DialogHandler as DialogHandler
import Examples.DiscordMessagingFuncs as funcs
import Examples.DiscordEvents as DiscordEvents
import logging

logger = logging.getLogger('discord')

class SimpleBot(Bot):
    def __init__(self, **kargs):
        super().__init__(**kargs)
        self.loaded = False
        self.main_menu_handler = DialogHandler.DialogHandler(bot=self)
        self.main_menu_handler.setup_from_files(["Examples/WalkthroughMenu.yaml"])
        self.main_menu_handler.register_module(funcs)
        # can instantiate more handlers to manage separate areas

    async def on_ready(self):
        if self.loaded:
            logger.info('reconnected as {0.user}'.format(self))
        else:
            logger.info('We have logged in as {0.user}'.format(self))
            self.main_menu_handler.start_cleaning(self.loop)

        
    async def on_interaction(self, interaction):
        #TODO: fill in once I know what to do with it, does the existing error of separate views with buttons with the same names not really being able to deal still exist in latest version?
        if interaction.type == InteractionType.component:
            await self.main_menu_handler.notify_event("button_click", interaction)