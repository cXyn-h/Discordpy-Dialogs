class Dialog:
    def __init__(self, args):
        print("dialog init internal",args)
        self.name = args["name"]
        #TODO: handle malformed input
        self.prompt= args["prompt"]
        self.command=""
        self.options={}
        if "options" in args:
            self.options = args["options"]
        if "command" in args:
            self.command = args["command"]

    def __repr__(self):
        return f"Dialog {self.name} prompt: {self.prompt}, options: {self.options}"

class Option:
    def __init__(self, args):
        self.label= args["label"]
        self.id = args["id"]
        self.command=""
        self.dialog=""
        self.flag=""
        self.data={}
        if "command" in args:
            self.command = args["command"]
        if "dialog" in args:
            self.dialog = args["dialog"]
        if "flag" in args:
            self.flag = args["flag"]
        if "data" in args:
            self.data = args["data"]
        if "end" in args:
            self.end = args["end"]
        else:
            self.end = False
    
    def __repr__(self):
        return f"option {self.label}"

    