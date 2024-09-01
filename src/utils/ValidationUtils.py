from src.utils.Enums import POSSIBLE_PURPOSES
class FunctionSectionInfo():
    def __init__(self, function_list=None, node_id=None, purpose=None, section_name=None, event_type=None) -> None:
        self.function_list = function_list if function_list is not None else []
        self.node_id = node_id
        self.section_name = section_name
        self.event_type = event_type
        self.purpose = purpose

