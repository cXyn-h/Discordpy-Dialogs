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

#TODO: discord ui elements styles can be defined in yaml files
class Option:
    def __init__(self, args):
        print("option init internal", args)
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
    def __init__(self, args):
        print("modal init internal",args)
        self.title = args["title"]
        self.name = args["name"]
        self.fields = {}
        self.submit_callback = ""
        self.next_node=""
        self.end = False
        if "fields" in args:
            self.fields = args["fields"]
        if "submit_callback" in args:
            self.submit_callback = args["submit_callback"]
        if "next_node" in args:
            self.next_node = args["next_node"]
        if "end" in args:
            self.end = args["end"]