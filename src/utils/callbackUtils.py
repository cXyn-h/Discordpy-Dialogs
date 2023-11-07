import copy
import yaml
import typing
import inspect
import os
from src.utils.Enums import POSSIBLE_PURPOSES
#TODO: implement allowed events
#TODO: implement allowed nodes
def callback_settings(schema:typing.Union[dict, str]=None, allowed_sections:'list[POSSIBLE_PURPOSES]'=None, has_parameter:typing.Literal["always", "optional", None]=None, 
                      cb_key:str=None, allowed_events:"list[str]"=None, allowed_nodes:"list[str]"=None):
    '''decorator to set all the settings for how to use function in callbacks. Records settings as attributes on function.
    has to be first in decorator list on a function. if can't, use builtin setattr or provided set_callback_settings
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file - that has schema to validate function input - relative from where file that holds function is. stores as loaded dictionary
    `allowed_sections` - list[POSSIBLE_PURPOSES]
        what section of callbacks that function is meant for. can be one of the four values for utils.Enums.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function
    allowed_events - list[str]
        WIP yet to implement, events that this function can handle'''
    return lambda func: set_callback_settings(func=func, schema=schema, allowed_sections=allowed_sections, 
                                              has_parameter=has_parameter, cb_key=cb_key, allowed_events=allowed_events, allowed_nodes=allowed_nodes)

def set_callback_settings(func, schema:typing.Union[dict, str]=None, allowed_sections:'list[POSSIBLE_PURPOSES]'=None, has_parameter:typing.Literal["always", "optional", None]=None, 
                          cb_key:str=None, allowed_events:"list[str]"=None, allowed_nodes:"list[str]"=None):
    '''function that sets all the settings for how to use function in callbacks. Records settings as attributes on function.
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file - that has schema to validate function input - relative from where file that holds function is. stores as loaded dictionary
    `allowed_sections` - list[POSSIBLE_PURPOSES]
        what section of callbacks that function is meant for. can be one of the four values for utils.Enums.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function
    allowed_events - list[str]
        WIP yet to implement, events that this function can handle'''
    filtered_allowed_sections = set()
    if allowed_sections is not None:
        for section in allowed_sections:
            if type(section) is POSSIBLE_PURPOSES:
                filtered_allowed_sections.add(section)
    func.allowed_sections = list(filtered_allowed_sections)
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
    func.has_parameter = has_parameter
    func.cb_key = cb_key or func.__name__
    func.allowed_events = allowed_events
    func.alowed_nodes = allowed_nodes
    return func
