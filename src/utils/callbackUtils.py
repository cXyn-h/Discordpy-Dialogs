import copy
import yaml
import typing
import inspect
import os
#TODO: implement allowed events
#TODO: implement allowed nodes
def callback_settings(schema:typing.Union[dict, str]=None, allowed:list=None, has_parameter:str=None, cb_key=None, allowed_events:list=None, allowed_nodes:list=None):
    '''decorator to record settings for how to use function in callbacks. Records settings as attributes on function
    has to be first in decorator list on a function. if can't, use builtin setattr or provided set_callback_settings
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file relative from where function is that has schema to validate function input. stores as loaded dictionary
    `allowed` - list[str]
        what section of callbacks that function is meant for. can be one of the four values for utils.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function
    allowed_events - list[str]
        WIP, events that this function can handle'''
    return lambda func: set_callback_settings(func=func, schema=schema, allowed=allowed, 
                                              has_parameter=has_parameter, cb_key=cb_key, allowed_events=allowed_events, allowed_nodes=allowed_nodes)

def set_callback_settings(func, schema:typing.Union[dict, str]=None, allowed:list=None, has_parameter:str=None, 
                          cb_key:str=None, allowed_events:list=None, allowed_nodes:list=None):
    '''function that sets the settings on the functions made for callbacks.
    
    Parameters
    ---
    `schema` - Union[dict, str]
        loaded schema or path to yaml file relative from where function is that has schema to validate function input. stores as loaded dictionary
    `allowed` - list[str]
        what section of callbacks that function is meant for. can be one of the four values for utils.POSSIBLE_PURPOSES enum: FILTER, ACTION, TRANSITION_FILTER, TRANSITION_ACTION
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function
    allowed_events - list[str]
        WIP, events that this function can handle'''
    func.allowed = allowed if allowed is not None else  []
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
