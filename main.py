import json

import discord
from discord.ext import commands
from Examples.ExampleBot import SimpleBot

intents = discord.Intents.default()
intents.message_content = True

bot = SimpleBot(command_prefix="$", intents=intents)

@bot.listen()
async def on_message(message: discord.Message):
    await bot.main_menu_handler.notify_event("message", message)

@bot.command()
async def menu(ctx):
    await bot.main_menu_handler.start_at("welcome", "message_command", ctx)

@bot.command()
async def reload_menu(ctx):
    bot.main_menu_handler.reload_files(["Examples/WalkthroughMenu.yaml"])
    await ctx.channel.send("reloaded!")

f = open("./config.json")
config_ops = json.load(f)

bot.run(config_ops["token"])