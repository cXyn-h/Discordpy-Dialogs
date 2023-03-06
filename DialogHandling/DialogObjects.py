#TODO: would base node class make things easier?
#TODO: add filtering for who is allowed to progress from this node
from discord import TextStyle

class DialogInfo:
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

    def __repr__(self):
        return f"Dialog {self.id} prompt: {self.prompt}, options: {self.options}"

class ReplyNodeInfo:
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

    def __repr__(self):
        return f"Reply {self.id} prompt: {self.prompt}"

#TODO: discord ui elements styles can be defined in yaml files
#TODO: support select menus as well as buttons
class OptionInfo:
    required_input=["id", "label"]
    optional_input=["command", "next_node", "end", "flag", "data"]
    def __init__(self, args):
        # print("option init internal", args)
        self.label= args["label"]
        self.id = args["id"]
        self.command=""
        self.next_node=""
        self.flag=""
        self.data={}
        self.end = False
        if "command" in args:
            self.command = args["command"]
        if "next_node" in args:
            self.next_node = args["next_node"]
            # print("option", self.id, "init set next node to ", self.next_node)
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
        if "end" in args:
            self.end = args["end"]
        # print("option init internal", args)
    
    def __repr__(self):
        return f"option {self.label}"

class ModalInfo:
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
            self.next_node = args["next_node"]
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
        if "end" in args:
            self.end = args["end"]

class ModalFieldInfo:
    required_input=["id", "label"]
    optional_input=["default_value", "max_length", "min_length", "placeholder", "required", "style", "value"]
    def __init__(self, args):
        self.id = args["id"]
        self.label = args["label"]
        self.default_value = ""
        self.max_length = 4000
        self.min_length = 0
        self.placeholder = ""
        self.required = False
        self.style = TextStyle.short

        if "default_value" in args:
            self.default_value = args["default_value"]
        if "max_length" in args:
            self.max_length = args["max_length"]
        if "min_length" in args:
            self.min_length = args["min_length"]
        if "placeholder" in args:
            self.placeholder = args["placeholder"]
        if "required" in args:
            self.required = args["required"]
        if "style" in args:
            self.style = args["style"]