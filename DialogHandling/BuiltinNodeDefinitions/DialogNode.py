import DialogHandling.DialogHandler as DialogHandler
class DialogLayout:
    required_input=["id"]
    optional_input=["prompt", "command", "options"]
    def __init__(self, args):
        # print("dialog init internal",args)
        self.id = args["id"]
        #TODO: handle malformed input
        self.prompt= args["prompt"]
        self.command=""
        self.options={}
        self.type = "dialog"
        if "options" in args:
            self.options = args["options"]
        if "command" in args:
            self.command = args["command"]

    async def do_node(self, handler, save_data, interaction_msg_or_context, passed_in_type, msg_options={}):
        #NOTE: This will probably need some changing to allow for channging channels to send in
        send_method = DialogHandler.interaction_send_message_wrapper(interaction_msg_or_context) \
                        if passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        if len(self.options) > 0:
            view = DialogHandler.DialogView(handler, self.id)
            dialog_message = await send_method(content=self.prompt, view=view, **msg_options)
            active_node = DialogNode(self, save_data, channel_message=dialog_message, view=view)
            return active_node
        else:
            # no options to choose from, meaning no waiting
            dialog_message = await send_method(content=self.prompt, **msg_options)
            return DialogNode(self, save_data, channel_message=dialog_message)

    def __repr__(self):
        return f"Dialog {self.id} prompt: {self.prompt}, options: {self.options}"
    
class DialogNode:
    def __init__(self, layout_node, save_data=None, channel_message=None, view=None):
        self.layout_node = layout_node
        self.save_data = save_data
        if len(self.layout_node.options) > 0:
            self.waits = ["interaction"]
        else:
            self.waits = []
        self.view = view
        self.channel_message = channel_message
        if self.view:
            self.view.interaction_check = self.filter_event
            view.mark_active_node(self)
        self.is_active = True
        self.replies = 0

        if len(self.layout_node.options) > 0:
            self.event_keys = {"interaction":channel_message.id}
        else:
            self.event_keys = {}

    def form_key(self, event):
        return event.message.id
    
    async def filter_event(self, event):
        if not event.data["custom_id"] in self.layout_node.options:
            return False
        if self.save_data: 
            if event.user.id != self.save_data["user"].id:
                return False
        return True
    
    async def process_event(self, handler, interaction):
        chosen_option = self.layout_node.options[interaction.data["custom_id"]] 
        changes = {}
        
        if chosen_option.data:
            if not "data" in changes:
                changes["data"] = {}
            changes["data"].update(chosen_option.data)
        if chosen_option.flag:
            changes["flag"] = chosen_option.flag
        self.replies += 1
        return (changes, chosen_option.command)

    async def get_chaining_info(self, interaction):
        # return none if not allowed to chain to node
        chosen_option = self.layout_node.options[interaction.data["custom_id"]]
        return (chosen_option.next_node, chosen_option.end)

    async def can_close(self):
        # TODO: assuming when need to close previous message for progression gets messy with end of chain no-option dialog nodes. 
        # This closes on every instance, need a better flag
        if self.save_data:
            return True
        return False
    
    async def close(self, was_fulfilled):
        if self.view:
            self.view.clear_items()
            if not was_fulfilled:
                await self.channel_message.edit(content="timed out please try again", view=self.view)
            else:
                await self.channel_message.edit(view=self.view)
            await self.view.stop()
            self.view = None
        self.is_active = False
        
