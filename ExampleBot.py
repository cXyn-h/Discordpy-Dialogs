import discord
from discord.ext import commands
from discord.ext.commands import Bot

from DialogHandling.DialogHandler import DialogHandler

class SimpleBot(Bot):
    def __init__(self, **kargs):
        super().__init__(**kargs)
        self.loaded = False
        self.dialog_handler = DialogHandler()
        self.dialog_handler.load_file("./testDialogs.yaml")

    async def on_ready(self):
        if self.loaded:
            print('reconnected as {0.user}'.format(self))
        else:
            print('We have logged in as {0.user}'.format(self))
