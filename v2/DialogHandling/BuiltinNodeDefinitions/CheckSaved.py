import v2.DialogHandling.DialogObjects as DialogObjects
import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing
import v2.DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions

class CheckSavedLayout:
    type = "CheckSaved"
    def __init__(self, args):
        # required fields
        self.id = args["id"]
        self.paths = args["paths"]
        self.next_node = ""
        self.command=""
        if "command" in args:
            self.command = args["command"]
        if "next_node" in args:
            self.next_node = args["next_node"]
        pass

    async def do_node(self, handler, save_data, interaction_msg_or_context, event_object_class, msg_options={}):
        return CheckSavedNode(self, save_data=save_data)

    @classmethod
    def parse_node(cls, yaml_node):
        if (not "paths" in yaml_node):
            # currently requiring all dialog nodes need a prompt
            raise Exception("Check saved state node missing prompt: "+ str(yaml_node))
        
        nested_definitions = []
        paths = []
        for yaml_path in yaml_node["paths"]:
            if not "key" in yaml_path:
                raise Exception("path choice missing key to check"+ str(yaml_path))
            
            if "next_node" in yaml_path:
                next_id, next_nested_nodes = DialogNodeParsing.parse_next_node_field(yaml_path["next_node"])
                nested_definitions.extend(next_nested_nodes)
                yaml_path["next_node"] = next_id
                paths.append(yaml_path)

        if "next_node" in yaml_node:
            next_id, next_nested_nodes = DialogNodeParsing.parse_next_node_field(yaml_node["next_node"])
            nested_definitions.extend(next_nested_nodes)
            yaml_node["next_node"] = next_id
        return (CheckSavedLayout({**yaml_node, "paths":paths}), nested_definitions)

class CheckSavedNode(BaseNodeDefinitions.BaseNode):
    def __init__(self, layout_node, save_data=None, channel_message=None):
        super().__init__(layout_node, save_data, channel_message)
        self.waits = ["automatic"]

    async def filter_event(self, event):
        return True

    async def process_event(self, handler, event):
        pass

    async def update_save(self, interaction, data_loc):
        pass

    async def get_chaining_info(self, event):
        if self.save_data:
            for path in self.layout_node.paths:
                if path["key"] not in self.save_data["data"]:
                    return path["next_node"]
        return self.layout_node.next_node

    async def post_chaining(self, chaining_status, next_node_layout):
        pass

    async def can_close(self):
        return True

    async def close(self, was_fulfilled):
        super().close(was_fulfilled=was_fulfilled)