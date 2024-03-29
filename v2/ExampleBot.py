import discord
from discord.ext import commands
from discord.ext.commands import Bot

from v2.DialogHandling.DialogHandler import DialogHandler
import logging
logger = logging.getLogger('discord')
class SimpleBot(Bot):
    def __init__(self, **kargs):
        super().__init__(**kargs)
        self.loaded = False
        self.dialog_handler = DialogHandler()
        self.dialog_handler.load_file("./testDialogs.yaml")
        # self.dialog_handler.load_file("./DialogDebuggingNodes.yaml")
    async def on_ready(self):
        if self.loaded:
            logger.info('reconnected as {0.user}'.format(self))
        else:
            logger.info('We have logged in as {0.user}'.format(self))
            self.dialog_handler.start_cleaning(self.loop)

    async def on_interaction(self, interaction):
        await self.dialog_handler.on_interaction(interaction)
