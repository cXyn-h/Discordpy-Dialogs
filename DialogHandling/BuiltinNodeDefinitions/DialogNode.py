import DialogHandling.DialogHandler as DialogHandler
import DialogHandling.DialogNodeParsing as DialogNodeParsing
import DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions

class DialogLayout(BaseNodeDefinitions.BaseLayout):
    required_input=["id"]
    optional_input=["prompt", "command", "options"]
    type = "dialog"
    def __init__(self, args):
        # print("dialog init internal",args)
        super().__init__(args)
        #TODO: handle malformed input
        self.prompt= args["prompt"]
        self.command=""
        self.options={}
        if "options" in args:
            self.options = args["options"]
        if "command" in args:
            self.command = args["command"]

    async def do_node(self, handler, save_data, interaction_msg_or_context, event_object_class, msg_options={}):
        #NOTE: This will probably need some changing to allow for channging channels to send in
        send_method = DialogHandler.interaction_send_message_wrapper(interaction_msg_or_context) \
                        if event_object_class == "Interaction" else interaction_msg_or_context.channel.send
        if len(self.options) > 0:
            view = DialogHandler.DialogView(handler, self.id)
            dialog_message = await send_method(content=self.prompt, view=view, **msg_options)
            active_node = DialogNode(self, save_data, channel_message=dialog_message, view=view)
            return active_node
        else:
            # no options to choose from, meaning no waiting
            dialog_message = await send_method(content=self.prompt, **msg_options)
            return DialogNode(self, save_data, channel_message=dialog_message)
        
    @classmethod
    def parse_node(cls, yaml_node):
        if (not "prompt" in yaml_node):
            # currently requiring all dialog nodes need a prompt
            raise Exception("dialog node missing prompt: "+ str(yaml_node))
        
        if "fields" in yaml_node:
            print("dialog node definition has fields defined in it. Note this will be ignored")

        nested_definitions = []
        options = {}
        # ensure any options for this dialog are loaded correctly before saving dialog
        if "options" in yaml_node:
            for yaml_option in yaml_node["options"]:
                loaded_option, nested_definitions = DialogNodeParsing.parse_option_field(yaml_option, yaml_node)
                if loaded_option.id in options:
                    raise Exception("option \""+loaded_option.id+"\" already defined for dialog node \""+yaml_node["id"]+"\"")
                options[loaded_option.id] = loaded_option
        return (DialogLayout({**yaml_node, "options":options}), nested_definitions)

    def __repr__(self):
        return f"Dialog {self.id} prompt: {self.prompt}, options: {self.options}"
    
class DialogNode(BaseNodeDefinitions.BaseNode):
    def __init__(self, layout_node, save_data=None, channel_message=None, view=None):
        super().__init__(layout_node, save_data, channel_message)
        if len(self.layout_node.options) > 0:
            self.waits = ["interaction"]
        else:
            self.waits = []
        self.view = view
        if self.view:
            self.view.interaction_check = self.filter_event
            view.mark_active_node(self)
        self.replies = 0
        self.needs_to_close = False

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
        self.replies += 1
        return chosen_option.command
    
    async def update_save(self, interaction, data_loc):
        chosen_option = self.layout_node.options[interaction.data["custom_id"]]
        if chosen_option.data:
            data_loc.update(chosen_option.data)
        if chosen_option.flag:
            data_loc["flag"] = chosen_option.flag

    async def get_chaining_info(self, interaction):
        # return none if not allowed to chain to node
        chosen_option = self.layout_node.options[interaction.data["custom_id"]]
        return (chosen_option.next_node, chosen_option.end)
    
    async def post_chaining(self, chaining_status, next_node_layout):
        if next_node_layout:
            if next_node_layout.type == self.layout_node.type:
                if self.save_data and len(next_node_layout.options) > 1:
                    self.needs_to_close = True
            else:
                if self.save_data:
                    self.needs_to_close = True
        else:
            self.needs_to_close = True

    async def can_close(self):
        # TODO: assuming when need to close previous message for progression gets messy with end of chain no-option dialog nodes. 
        # This closes on every instance, need a better flag
        return self.needs_to_close
    
    async def close(self, was_fulfilled):
        if self.view:
            self.view.clear_items()
            if not was_fulfilled:
                await self.channel_message.edit(content="timed out please try again", view=self.view)
            else:
                await self.channel_message.edit(view=self.view)
            await self.view.stop()
            self.view = None
        await super().close(was_fulfilled)
        
