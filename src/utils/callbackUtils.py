def callback_settings(documentation={}, allowed=[], has_parameter:str=None, cb_key=None):
    '''decorator to record settings for how to use function in callbacks. Records settings as attributes on function
    has to be first in decorator list on a function. if can't, use builtin setattr or provided set_callback_settings
    
    Parameters
    ---
    `documentation` - dict
        WIP, doesn't do anything yet. meant to be schema and documentation to verify that yaml files are correctly formatted
    `allowed` - list[str]
        what section of callbacks that function is meant for. can be "filter", "callback", "transition_filter", or "transition_callback"
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function'''
    return lambda func: set_callback_settings(func=func, documentation=documentation, allowed=allowed, has_parameter=has_parameter, cb_key=cb_key)

def set_callback_settings(func, documentation={}, allowed=[], has_parameter:str=None, cb_key:str=None):
    '''function that sets the settings on the functions made for callbacks.
    
    Parameters
    ---
    `documentation` - dict
        WIP, doesn't do anything yet. meant to be schema and documentation to verify that yaml files are correctly formatted
    `allowed` - list[str]
        what section of callbacks that function is meant for. can be "filter", "callback", "transition_filter", or "transition_callback"
    `has_parameter` - "always", "optional" or None
        whether the function always needs, optionally takes, or never takes a parameter
    `cb_key` - str
        key that will be used in yaml to specify this function'''
    func.allowed = allowed
    func.documentation = documentation
    func.has_parameter = has_parameter
    func.cb_key = cb_key or func.__name__
    return func
