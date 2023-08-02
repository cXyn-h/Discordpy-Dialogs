import v2.DialogHandling.DialogHandler as DialogHandler
from discord import ComponentType, TextStyle
import v2.DialogHandling.DialogObjects as DialogObjects
import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing
import v2.DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions

class ModalLayout(BaseNodeDefinitions.BaseGraphNode):
    required_input=["id", "title"]
    optional_input=["fields", "submit_callback", "next_node", "end"]
    type = "modal"
    def __init__(self, args):
        # print("modal init internal",args)
        super().__init__(args)
        self.title = args["title"]
        self.fields = {}
        self.submit_callback = ""
        self.next_node=""
        self.flag=""
        self.data={}
        self.end = False
        if "fields" in args:
            self.fields = args["fields"]
        if "submit_callback" in args:
            self.submit_callback = args["submit_callback"]
        if "next_node" in args:
            print("sanity check", args["id"], args["next_node"])
            self.next_node = args["next_node"]
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
        if "end" in args:
            self.end = args["end"]

    async def do_node(self, handler, save_data, interaction, event_object_class, msg_options={}):
        modal = DialogHandler.DialogModal(handler, self.id)
        await interaction.response.send_modal(modal)
        return ModalNode(self, interaction, save_data, channel_message = interaction.message, modal=modal)
    
    @classmethod
    def parse_node(cls, yaml_node):
        if (not "title" in yaml_node):
            # basically all modals must have a separate title to display to all interacters
            raise Exception("modal node missing title "+str(yaml_node))
        
        if "options" in yaml_node:
            print("modal node", yaml_node["id"],"definition has options defined in it. Note this will be ignored")

        nested_definitions = []
        fields = {}
        if "fields" in yaml_node:
            for yaml_field in yaml_node["fields"]:
                if (not "label" in yaml_field) or (not "id" in yaml_field):
                    raise Exception("modal node \""+yaml_node["id"]+"\" has mis formed field" + yaml_field )
                if yaml_field["id"] in fields:
                    raise Exception("field \""+yaml_field["id"]+"\" already defined for modal node \"" + yaml_node["id"] + "\"")
                if "style" in yaml_field:
                    if yaml_field["style"] == "paragraph":
                        yaml_field["style"] = TextStyle.paragraph
                    elif yaml_field["style"] == "long":
                        yaml_field["style"] = TextStyle.paragraph
                    else:
                        yaml_field["style"] = TextStyle.short
                fields[yaml_field["id"]] = DialogObjects.ModalFieldInfo(yaml_field)
        if len(fields) < 1 or len(fields) > 5:
            raise Exception(f"modal {yaml_node['id']} has wrong number of fields, must be between 1 and 5, but currently has {len(fields)}")
        
        if "next_node" in yaml_node:
            next_id, nested_definitions = DialogNodeParsing.parse_next_node_field(yaml_node["next_node"])
            yaml_node["next_node"] = next_id
        return (ModalLayout({**yaml_node, "fields":fields}), nested_definitions)

class ModalNode(BaseNodeDefinitions.BaseNode):
    def __init__(self, layout_node, interaction, save_data=None, channel_message=None, modal=None):
        super().__init__(layout_node, save_data, channel_message)
        self.waits = ["modal_submit"]
        self.modal = modal
        self.reply_messages = []
        self.replies = 0

        self.event_keys = {"modal_submit":(interaction.user.id, self.layout_node.id)}

    def form_key(self, event):
        return (event.user.id, self.layout_node.id)

    async def filter_event(self, event):
        return True
    
    async def process_event(self, handler, interaction):
         #TODO: parse submitted info and save
        self.reply_messages.append(interaction)
        self.replies += 1
        return self.layout_node.submit_callback
    
    async def update_save(self, interaction, data_loc):
        if self.layout_node.data:
            data_loc.update(self.layout_node.data)
        if self.layout_node.flag:
            data_loc["flag"] = self.layout_node.flag
        submission = interaction.data["components"]
        for ui_element in submission:
            # if ui_element["type"] == ComponentType.text_input: # comparison doesn't seem to work for some reasion. because can't find componenttype enum?
            element_data = ui_element["components"][0]
            customid = [x for x,y in self.layout_node.fields.items() if y.label == element_data["custom_id"]][0]
            data_loc.update({customid:element_data["value"]})
    
    async def get_chaining_info(self, interaction):
        return (self.layout_node.next_node, self.layout_node.end)
    
    async def post_chaining(self, chaining_status, next_node_layout):
        pass
    
    async def can_close(self):
        return self.replies > 0

    async def close(self, was_fulfilled):
        await super().close(was_fulfilled=was_fulfilled)