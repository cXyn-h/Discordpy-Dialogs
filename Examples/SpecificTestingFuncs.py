import Examples.DiscordMessagingFuncs as DiscordFuncs

def save_quiz_answer(active_node, event, goal_node):
    if goal_node.session is None:
        return
    if "quiz" not in goal_node.session:
        goal_node.session["quiz"] = {}    
    goal_node.session["quiz"][active_node.graph_node.id] = event.data["custom_id"]

async def report_quiz_answers(active_node, event):
    if active_node.session is None:
        return
    message_to_send = "Here is what you responded:"+ "\n".join([k+": "+v for k,v in active_node.session["quiz"].items()])
    if hasattr(active_node, "message") and active_node.message is not None:
        await active_node.message.edit(content = message_to_send)
    else:
        await DiscordFuncs.send_response(active_node, event, message_settings={"content":message_to_send})
        

dialog_func_info= {save_quiz_answer:["transition_callback"], report_quiz_answers:["callback"]}