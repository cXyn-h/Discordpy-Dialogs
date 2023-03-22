import DialogHandling.DialogHandler as DialogHandler
class ReplyLayout:
    required_input=["id"]
    optional_input=["prompt", "submit_callback", "next_node", "end"]
    def __init__(self, args):
        # print("dialog init internal",args)
        self.id = args["id"]
        self.prompt= ""
        self.submit_callback = ""
        self.next_node=""
        self.flag=""
        self.data={}
        self.end = False
        self.type = "reply"
        if "prompt" in args:
            self.prompt = args["prompt"]
        if "submit_callback" in args:
            self.submit_callback = args["submit_callback"]
        if "next_node" in args:
            self.next_node = args["next_node"]
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
        if "end" in args:
            self.end = args["end"]

    async def do_node(self, handler, save_data, interaction_msg_or_context, passed_in_type, msg_options={}):
        send_method = DialogHandler.interaction_send_message_wrapper(interaction_msg_or_context) \
                        if passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        msg_contents = self.prompt if self.prompt else "Please type response in chat"
        prompt_message = await send_method(content=msg_contents, **msg_options)
        return ReplyNode(self, save_data, channel_message=prompt_message)
    
    def __repr__(self):
        return f"Reply {self.id} prompt: {self.prompt}"
    
class ReplyNode:
    def __init__(self, layout_node, save_data=None, channel_message=None):
        self.layout_node = layout_node
        self.save_data = save_data
        self.waits = ["reply"]
        self.channel_message = channel_message
        self.reply_messages = []
        self.replies = 0
        self.is_active = True

        self.event_keys = {"reply":channel_message.id}

    def form_key(self, event):
        if event.reference:
            return event.reference.message_id
        return None

    async def filter_event(self, event):
        if not event.reference:
            return False
        if event.reference.message_id == self.channel_message.id:
            if self.save_data:
                if self.save_data["user"].id == event.author.id:
                    return True
                else:
                    return False
            else:
                return True
        return False

    async def process_event(self, handler, message):
        #TODO: fancy filtering what part of message want to save
        changes = {"reply":message.content}
        self.reply_messages.append(message)
        if self.layout_node.data:
            if not "data" in changes:
                changes["data"] = {}
            changes["data"].update(self.layout_node.data)
        if self.layout_node.flag:
            changes["flag"] = self.layout_node.flag
        self.replies += 1
        return (changes, None)

    async def get_chaining_info(self, message):
        return (self.layout_node.next_node, self.layout_node.end)

    async def can_close(self):
        return len(self.reply_messages) > 0

    async def close(self, was_fulfilled):
        if not was_fulfilled:
            await self.channel_message.edit(content="timed out. please try again")
        self.is_active = False