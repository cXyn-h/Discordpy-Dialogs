from datetime import datetime, timedelta

class BaseLayout:
    type = "FILL IN WITH YOUR TYPE, UNIQUE KEY AMONG ALL NODES USED"
    def __init__(self, args):
        '''call from parsing after formatting things correctly. The exact format and number for fields specific to this node is up to designer.
        Just make sure active node is accessing the right fields when the data is needed.
        Some fields are common across all nodes. `id` is expected to be hashable key for each layout node object loaded into the same handler. `type`
        is usually a string to represent type. `next_node` can be in node or sub fields, it must be the id of the next node.'''
        # required fields
        self.id = args["id"]

    async def do_node(self, handler, save_data, interaction_msg_or_context, event_object_class, msg_options={}):
        pass

    @classmethod
    def parse_node(cls, yaml_node):
        pass

class BaseNode:
    def __init__(self, layout_node, save_data=None, channel_message=None, timeout_duration=timedelta(minutes=3)):
        self.layout_node = layout_node
        self.save_data = save_data
        self.channel_message = channel_message
        self.timeout = datetime.utcnow() + timeout_duration
        self.waits = []
        self.is_active = True

    async def filter_event(self, event):
        pass

    async def process_event(self, handler, event):
        pass

    async def update_save(self, interaction, data_loc):
        pass

    async def get_chaining_info(self, interaction):
        pass

    async def post_chaining(self, chaining_status, next_node_layout):
        pass

    async def can_close(self):
        pass

    async def close(self, was_fulfilled):
        self.is_active = False