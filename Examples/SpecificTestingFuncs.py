import discord
import Examples.DiscordMessagingFuncs as DiscordFuncs

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
    

async def report_quiz_answers(active_node, event):
    if active_node.session is None:
        return
    message_to_send = "Here is what you responded:\n"+ "\n".join([k+": "+str(v) for k,v in active_node.session.data["quiz"].items()])
    if hasattr(active_node, "message") and active_node.message is not None:
        await active_node.message.edit(content = message_to_send)
    else:
        await DiscordFuncs.send_message(active_node, event, settings={"use_reply": True, "message":{"content":message_to_send}})
        

dialog_func_info= {save_quiz_answer:["transition_callback"], report_quiz_answers:["callback"]}