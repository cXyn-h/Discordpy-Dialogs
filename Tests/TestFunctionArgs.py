import src.utils.callbackUtils as cbUtils

@cbUtils.callback_settings(allowed=["callback", "filter"])
def f1(a, e):
    if a != "a" or e != "e":
        raise Exception(f"f1 Bad values")

@cbUtils.callback_settings(allowed=["callback", "filter"])
def f2(a, e, v=None):
    if a != "a" or e != "e":
        raise Exception(f"f2 Bad values")
    print(f"f2 received a value of {v}")

@cbUtils.callback_settings(allowed=["callback", "filter"])
def f3(a, e, v):
    if a != "a" or e != "e" or v != "v":
        raise Exception(f"f3 Bad values")
    print(f"f3 received a value of {v}")

@cbUtils.callback_settings(allowed=["transition_filter", "transition_callback"])
def f4(a, e, g):
    if a != "a" or e != "e" or g != "g":
        raise Exception(f"f4 Bad values")

@cbUtils.callback_settings(allowed=["transition_filter", "transition_callback"])
def f5(a, e, g, v=None):
    if a != "a" or e != "e" or g != "g":
        raise Exception(f"f5 Bad values")
    print(f"f5 received a value of {v}")

@cbUtils.callback_settings(allowed=["transition_filter", "transition_callback"])
def f6(a,e,g,v):
    if a != "a" or e != "e" or g != "g" or v != "v":
        raise Exception(f"f6 Bad values")
    print(f"f6 received a value of {v}")

@cbUtils.callback_settings(allowed=["callback", "filter", "transition_filter", "transition_callback"])
def f7(a, e, g=None):
    if a != "a" or e != "e":
        raise Exception(f"f7 Bad values")
    print(f"f7 received a next_node of {g}")

@cbUtils.callback_settings(allowed=["callback", "filter", "transition_filter", "transition_callback"])
def f8(a, e, g=None, v=None):
    if a != "a" or e != "e":
        raise Exception(f"f1 Bad values")
    print(f"f2 received a next_node of {g} and a value of {v}")

@cbUtils.callback_settings(allowed=["callback", "filter", "transition_filter", "transition_callback"])
def f9(a, e, v, g=None):
    if a != "a" or e != "e" or v != "v":
        raise Exception(f"f9 Bad values")
    print(f"f9 received a next_node of {g}")

dialog_func_info = {f1:{}, f2:{}, f3:{}, f4:{}, f5:{}, f6:{}, f7:{},  f8:{}, f9:{}}

# possible configurations for parameters
# non-transition
# a, e
# a, e, v=None
# a, e, v                   #ban?
# tansition, g must be there
# a, e, g
# a, e, g, v=None
# a, e, g, v                #ban?
# either transition or not
# a, e, g=None
# a, e, g=None, v=None
# a, e, v, g=None           #the tricky one, don't know if I can identify this case. might be easier to always require v=None if accepting variables
# probalby only hard to sort out this case if don't know variable names

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.DialogHandler as DialogHandler
h = DialogHandler.DialogHandler()
for func, overrides in dialog_func_info.items():
    h.register_function(func, overrides)
#for verifying function arguments, currently just printing them out to manually make sure
for target_func in [f1, f2, f3, f4, f5, f6, f7, f8, f9]:
    for purpose in ["filter", "transition_filter"]:
        for parameter_set in [["a","e"], ["a","e","g"], ["a","e", None, "v"], ["a","e","g","v"]]:
            print(f"---targeting {target_func.__name__} purpose {purpose}, with {parameter_set}")
            try:
                arg_list = h.format_parameters(target_func.__name__, purpose, *parameter_set)
                print("---returned arg list is", arg_list)
                target_func(*arg_list)
            except Exception as e:
                print(f"---exception {e}")
