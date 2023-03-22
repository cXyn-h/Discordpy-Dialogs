import json

import discord
from discord.ext import commands
from ExampleBot import SimpleBot

intents = discord.Intents.default()
intents.message_content = True

bot = SimpleBot(command_prefix="!", intents=intents)

@bot.listen()
async def on_message(message: discord.Message):
    await bot.dialog_handler.on_message(message)

@bot.command()
async def test(ctx):
    await bot.dialog_handler.start_at("welcome", ctx)

@bot.command()
async def testmr(ctx):
    await bot.dialog_handler.start_at("sendMRStart", ctx)

@bot.command()
async def debugnodes(ctx):
    await bot.dialog_handler.start_at("starter", ctx)


f = open("./config.json")
config_ops = json.load(f)

bot.run(config_ops["token"])