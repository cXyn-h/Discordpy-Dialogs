import v2.DialogHandling.DialogHandler as DialogHandler
import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing
import v2.DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions

class ReplyLayout(BaseNodeDefinitions.BaseGraphNode):
    required_input=["id"]
    optional_input=["prompt", "submit_callback", "next_node", "end"]
    type = "reply"
    def __init__(self, args):
        # print("dialog init internal",args)
        super().__init__(args)
        self.prompt= ""
        self.submit_callback = ""
        self.next_node=""
        self.flag=""
        self.data={}
        self.end = False
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

    async def do_node(self, handler, save_data, interaction_msg_or_context, event_object_class, msg_options={}):
        send_method = DialogHandler.interaction_send_message_wrapper(interaction_msg_or_context) \
                        if event_object_class == "Interaction" else interaction_msg_or_context.channel.send
        msg_contents = self.prompt if self.prompt else "Please type response in chat"
        prompt_message = await send_method(content=msg_contents, **msg_options)
        return ReplyNode(self, save_data, channel_message=prompt_message)
    
    @classmethod
    def parse_node(cls, yaml_node):
        nested_definitions = []
        if "next_node" in yaml_node:
            next_id, nested_definitions = DialogNodeParsing.parse_next_node_field(yaml_node["next_node"])
            yaml_node["next_node"] = next_id
        return (ReplyLayout(yaml_node),nested_definitions)
    
    def __repr__(self):
        return f"Reply {self.id} prompt: {self.prompt}"
    
class ReplyNode(BaseNodeDefinitions.BaseNode):
    def __init__(self, layout_node, save_data=None, channel_message=None):
        super().__init__(layout_node, save_data, channel_message)
        self.waits = ["reply"]
        self.reply_messages = []
        self.replies = 0

        # was tested at some point but doesn't seem feasible so far. not in use
        self.event_keys = {"reply":channel_message.id}

    def form_key(self, event):
        # was tested at some point but doesn't seem feasible so far. not in use
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
        self.reply_messages.append(message)
        self.replies += 1
        return None
    
    async def update_save(self, message, data_loc):
        data_loc[self.layout_node.id] = message.content
        if self.layout_node.data:
            data_loc.update(self.layout_node.data)
        if self.layout_node.flag:
            data_loc["flag"] = self.layout_node.flag

    async def get_chaining_info(self, message):
        return (self.layout_node.next_node, self.layout_node.end)
    
    async def post_chaining(self, chaining_status, next_node_layout):
        pass

    async def can_close(self):
        return len(self.reply_messages) > 0

    async def close(self, was_fulfilled):
        if not was_fulfilled:
            await self.channel_message.edit(content="timed out. please try again")
        await super().close(was_fulfilled=was_fulfilled)