import copy

from src.utils.Enums import POSSIBLE_PURPOSES

class SubSection:
    pass
    
class IfSubSection(SubSection):
    def __init__(self, filters=None, actions=None):
        self.actions = actions if actions is not None else []
        self.filters = filters if filters is not None else []
        self.name = "if"
    
    def serialize(self):
        return {"if": {"actions": serialize_section(self.actions), "filters": serialize_section(self.filters)}}

class LogicOpSubSection(SubSection):
    def __init__(self, name, callbacks=None) -> None:
        self.name = name
        self.callbacks = callbacks if callbacks is not None else []

    def serialize(self):
        return {self.name: serialize_section(self.callbacks)}

def formatSection(section, purpose:POSSIBLE_PURPOSES):
    for index, item in enumerate(section):
        # also do some normailzation of input format
        if type(item) is str:
            # if string that means function call without parameters, might as well make it like other function calls
            func_name = item
            section[index] = {func_name: None}
        else:
            # dictionary because function call
            func_name = list(item.keys())[0]
            args = item[func_name]

            if is_handler_structure(func_name, purpose):
                # describes a subsection
                if func_name in ["if"]:
                    subsection = IfSubSection(filters=formatSection(args["filters"], purpose=POSSIBLE_PURPOSES.FILTER), actions=formatSection(args["actions"], purpose))
                    section[index] = subsection
                else:
                    section[index] = LogicOpSubSection(name=func_name, callbacks=formatSection(args, purpose))
    return section

def serialize_section(section):
    serialized = []
    for item in section:
        if issubclass(item.__class__, SubSection):
            serialized.append(item.serialize())
        else:
            serialized.append(copy.deepcopy(item))
    return serialized

def is_handler_structure(func_name, purpose:POSSIBLE_PURPOSES):
    if purpose in [POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER] and func_name in ["and", "or", "not"]:
        return True
    if purpose in [POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION] and func_name in ["if"]:
        return True
    return False