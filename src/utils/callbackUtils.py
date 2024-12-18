import copy
import yaml
import typing
import inspect
import os
from src.utils.Enums import POSSIBLE_PURPOSES
#TODO: implement allowed events
#TODO: implement allowed nodes
def callback_settings(schema:typing.Union[dict, str]=None, allowed_purposes:'list[POSSIBLE_PURPOSES]'=None, runtime_input_key:typing.Optional[str]=None, 
                      cb_key:str=None, description_blurb="", allowed_events:"list[str]"=None, allowed_nodes:"list[str]"=None):
    '''decorator to set all the settings for how to use function in callbacks. Records settings as attributes on function.
    Has to be first in decorator list on a function. if can't, use builtin setattr or provided set_callback_settings
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file - that has schema to validate function input - relative from where file that holds function is. stores as loaded dictionary
    `allowed_purposes` - list[POSSIBLE_PURPOSES]
        what section of callbacks that function is meant for. can be one of the four values for utils.Enums.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `runtime_input_key` - str or None
        name of key this callback will accept parameters from runtime at
    `cb_key` - str
        per function setting for the key that will be used in yaml to specify this function, overrideable by individual handlers
    allowed_events - list[str]
        WIP yet to implement, events that this function can handle
    allowed_nodes - list[str]
        WIP yet to implement, node types that can use this function'''
    return lambda func: set_callback_settings(func=func, schema=schema, allowed_purposes=allowed_purposes, 
                                              runtime_input_key=runtime_input_key, cb_key=cb_key, description_blurb=description_blurb, allowed_events=allowed_events, allowed_nodes=allowed_nodes)

def set_callback_settings(func, schema:typing.Union[dict, str]=None, allowed_purposes:'list[POSSIBLE_PURPOSES]'=None, runtime_input_key:typing.Optional[str]=None, 
                          cb_key:str=None, description_blurb="", allowed_events:"list[str]"=None, allowed_nodes:"list[str]"=None):
    '''function that sets all the settings for how to use function in callbacks. Records settings as attributes on function.
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file - that has schema to validate function input - relative from where file that holds function is. stores as loaded dictionary
    `allowed_purposes` - list[POSSIBLE_PURPOSES]
        what section of callbacks that function is meant for. can be one of the four values for utils.Enums.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `runtime_input_key` - str or None
        name of key this callback will accept parameters from runtime at
    `cb_key` - str
        per function setting for the key that will be used in yaml to specify this function, overrideable by individual handlers
    allowed_events - list[str]
        WIP yet to implement, events that this function can handle
    allowed_nodes - list[str]
        WIP yet to implement, node types that can use this function'''
    filtered_allowed_sections = set()
    if allowed_purposes is not None:
        for purpose in allowed_purposes:
            if type(purpose) is POSSIBLE_PURPOSES:
                filtered_allowed_sections.add(purpose)
    func.allowed_purposes = list(filtered_allowed_sections)
    if type(schema) is str:
        stk = inspect.stack()[1]
        mod = inspect.getmodule(stk[0])
        if mod.__file__.find("/") >= 0:
            split_module_path = mod.__file__.split("/") 
        else:   
            split_module_path = mod.__file__.split("\\")
        real_path = os.path.abspath(os.path.join("/".join(split_module_path[:-1]), schema))
        schema = yaml.safe_load(open(real_path))
    func.schema = schema if schema is not None else {}
    func.runtime_input_key = runtime_input_key
    func.cb_key = cb_key or func.__name__
    func.allowed_events = allowed_events if allowed_events else []
    func.alowed_nodes = allowed_nodes if allowed_nodes else []
    func.description_blurb= description_blurb
    return func

def is_callback_setup(func):
    return hasattr(func, "schema") and hasattr(func, "allowed_purposes") and hasattr(func, "runtime_input_key") and hasattr(func, "cb_key")  and \
            hasattr(func, "allowed_events") and hasattr(func, "allowed_nodes")

class CallbackDatapack():
    '''class that will hold all data that is being passed to each callback'''
    def __init__(self, active_node, event, base_parameter, goal_node_name=None, goal_node=None, section_data=None, section_name="", control_data=None, section_progress=None, **kwargs):
        self.active_node = active_node
        self.event = event
        self.goal_node_name = goal_node_name
        self.goal_node = goal_node
        self.base_parameter = base_parameter
        self.section_name = section_name
        self.section_data = section_data if section_data is not None else {}
        self.control_data = control_data if control_data is not None else {}
        self.section_progress = section_progress if section_progress is not None else {}

        for option, data in kwargs.items():
            setattr(self, option, data)