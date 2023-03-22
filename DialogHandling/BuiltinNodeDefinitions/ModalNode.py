import DialogHandling.DialogHandler as DialogHandler
from discord import ComponentType
class ModalLayout:
    required_input=["id", "title"]
    optional_input=["fields", "submit_callback", "next_node", "end"]
    def __init__(self, args):
        # print("modal init internal",args)
        self.title = args["title"]
        self.id = args["id"]
        self.fields = {}
        self.submit_callback = ""
        self.next_node=""
        self.flag=""
        self.data={}
        self.end = False
        self.type = "modal"
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

    async def do_node(self, handler, save_data, interaction, passed_in_type, msg_options={}):
        modal = DialogHandler.DialogModal(handler, self.id)
        await interaction.response.send_modal(modal)
        return ModalNode(self, interaction, save_data, channel_message = interaction.message, modal=modal)

class ModalNode:
    def __init__(self, layout_node, interaction, save_data=None, channel_message=None, modal=None):
        self.layout_node = layout_node
        self.save_data = save_data
        self.waits = ["modal"]
        self.modal = modal
        self.channel_message = channel_message
        self.reply_messages = []
        self.replies = 0
        self.is_active = True

        self.event_keys = {"modal":(interaction.user.id, self.layout_node.id)}

    def form_key(self, event):
        return (event.user.id, self.layout_node.id)

    async def filter_event(self, event):
        return True
    
    async def process_event(self, handler, interaction):
        changes = {}
        #TODO: parse submitted info and save
        self.reply_messages.append(interaction)
        if not "data" in changes:
            changes["data"] = {}
        if self.layout_node.data:
            changes["data"].update(self.layout_node.data)
        if self.layout_node.flag:
            changes["flag"] = self.layout_node.flag

        submission = interaction.data["components"]
        for ui_element in submission:
            # if ui_element["type"] == ComponentType.text_input: # comparison doesn't seem to work for some reasion. because can't find componenttype enum?
            element_data = ui_element["components"][0]
            customid = [x for x,y in self.layout_node.fields.items() if y.label == element_data["custom_id"]][0]
            changes["data"].update({customid:element_data["value"]})
        self.replies += 1
        return (changes, self.layout_node.submit_callback)
    
    async def get_chaining_info(self, interaction):
        return (self.layout_node.next_node, self.layout_node.end)
    
    async def can_close(self):
        return self.replies > 0

    async def close(self, was_fulfilled):
        self.is_active = False