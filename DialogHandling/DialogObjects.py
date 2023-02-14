class Dialog:
    name=""
    prompt=""
    command=""
    options={}

    def __init__(self, args):
        print("dialog init internal",args)
        self.name = args["name"]
        #TODO: handle malformed input
        self.prompt= args["prompt"]
        if "options" in args:
            self.options = args["options"]
        if "command" in args:
            self.command = args["command"]

    def __repr__(self):
        return f"Dialog {self.name} prompt: {self.prompt}, options: {self.options}"

class Option:
    label=""
    id=""
    command=""
    dialog=""
    flag=""
    data={}

    def __init__(self, args):
        self.label= args["label"]
        self.id = args["id"]
        if "command" in args:
            self.command = args["command"]
        if "dialog" in args:
            self.dialog = args["dialog"]
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
    
    def __repr__(self):
        return f"option {self.label}"

    