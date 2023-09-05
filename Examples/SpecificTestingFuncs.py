import discord
from discord import ui, InteractionType, Interaction
import Examples.DiscordMessagingFuncs as DiscordFuncs
import src.utils.callbackUtils as cbUtils
import Examples.DiscordUtils as DiscordUtils
from src.utils.Enums import POSSIBLE_PURPOSES

# Yep these functions are less generalized, probably similar to what another developer would want to add if customizing

def save_quiz_answer(active_node, event, goal_node):
    if goal_node.session is None:
        return
    if "quiz" not in goal_node.session.data:
        goal_node.session.data["quiz"] = {}
    if isinstance(event,discord.Message):
        goal_node.session.data["quiz"][active_node.graph_node.id] = event.content
    else:
        if event.data["component_type"] == discord.ComponentType.button.value:
            goal_node.session.data["quiz"][active_node.graph_node.id] = event.data["custom_id"]
        elif event.data["component_type"] == discord.ComponentType.select.value:
            goal_node.session.data["quiz"][active_node.graph_node.id] = event.data["values"]
cbUtils.set_callback_settings(save_quiz_answer, allowed=[POSSIBLE_PURPOSES.TRANSITION_ACTION])
    

async def report_quiz_answers(active_node, event):
    if active_node.session is None:
        return
    message_to_send = "Here is what you responded:\n"+ "\n".join([k+": "+str(v) for k,v in active_node.session.data["quiz"].items()])
    if hasattr(active_node, "message") and active_node.message is not None:
        await active_node.message.edit(content = message_to_send)
    else:
        await DiscordFuncs.send_message(active_node, event, settings={"use_reply": True, "message":{"content":message_to_send}})
cbUtils.set_callback_settings(report_quiz_answers, allowed=[POSSIBLE_PURPOSES.ACTION])


@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.ACTION])
async def dropbox_save_message(active_node, event):
    active_node.dropbox_message = event

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.ACTION])
async def dropbox_send_message(active_node, event, settings):
    bot = active_node.handler.bot

    channel = await bot.fetch_channel(settings["redirect"]["dest_channel_id"])
    copy_message = {k:getattr(active_node.dropbox_message,k) for k in ["content"]}
    #NOTE: fixes error with trying to copy attachments, not sure if there's other caveats to this
    copy_message["files"] = [await attachment.to_file() for attachment in  active_node.dropbox_message.attachments]
    embed = discord.Embed(
            timestamp=active_node.dropbox_message.created_at,
            color=0x663399)
    embed.set_author(name=f"{active_node.dropbox_message.author} ({active_node.dropbox_message.author.id})",
                        icon_url=active_node.dropbox_message.author.display_avatar.url)
    embed.add_field(name="Author link", value=active_node.dropbox_message.author.mention)
    embeds_list = [*active_node.dropbox_message.embeds]
    embeds_list.append(embed)
    copy_message["embeds"] = embeds_list
    await channel.send(**copy_message)

    message_components = DiscordUtils.build_discord_message(settings["redirect"]["message"], active_node.graph_node.TTL)
    if "use_reply" in settings:
        print(f"using reply, will it ping? {True if settings['use_reply'] == 'ping' else False}")
        sent_message = await event.reply(**message_components, allowed_mentions=discord.AllowedMentions(replied_user=True if settings["use_reply"] == "ping" else False))
    else:
        sent_message = await event.channel.send(**message_components)

dialog_func_info= {save_quiz_answer:{}, report_quiz_answers:{}, dropbox_save_message:{}, dropbox_send_message:{}}