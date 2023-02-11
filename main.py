import json

import discord
from discord.ext import commands
from ExampleBot import SimpleBot

intents = discord.Intents.default()
intents.message_content = True

bot = SimpleBot(command_prefix="!", intents=intents)

@bot.command()
async def test(ctx):
    await bot.dialog_handler.send_dialog(ctx.channel.send, "welcome")

f = open("./config.json")
config_ops = json.load(f)

bot.run(config_ops["token"])