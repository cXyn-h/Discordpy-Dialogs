#TODO: future: would base node class make things easier?
from discord import TextStyle

#TODO: soon: Discord ui elements styles can be defined in yaml files
#TODO: soon: support select menus as well as buttons
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
