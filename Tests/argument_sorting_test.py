import src.DialogHandler as DialogHandler
import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import src.utils.CallbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES
import pytest
import yaml

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER])
def f1(a, e):
    if a != "a" or e != "e":
        raise Exception(f"f1 Bad values")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER], runtime_input_key="optional")
def f2(a, e, v=None):
    if a != "a" or e != "e":
        raise Exception(f"f2 Bad values")
    print(f"f2 received a value of {v}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER], runtime_input_key="always")
def f3(a, e, v):
    if a != "a" or e != "e" or v != "v":
        raise Exception(f"f3 Bad values")
    print(f"f3 received a value of {v}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION])
def f4(a, e, g):
    if a != "a" or e != "e" or g != "g":
        raise Exception(f"f4 Bad values")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="optional")
def f5(a, e, g, v=None):
    if a != "a" or e != "e" or g != "g":
        raise Exception(f"f5 Bad values")
    print(f"f5 received a value of {v}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="always")
def f6(a,e,g,v):
    if a != "a" or e != "e" or g != "g" or v != "v":
        raise Exception(f"f6 Bad values")
    print(f"f6 received a value of {v}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION])
def f7(a, e, g=None):
    if a != "a" or e != "e":
        raise Exception(f"f7 Bad values")
    print(f"f7 received a next_node of {g}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="optional")
def f8(a, e, g=None, v=None):
    if a != "a" or e != "e":
        raise Exception(f"f1 Bad values")
    print(f"f2 received a next_node of {g} and a value of {v}")

@cbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.FILTER, POSSIBLE_PURPOSES.TRANSITION_FILTER, POSSIBLE_PURPOSES.TRANSITION_ACTION], runtime_input_key="always")
def f9(a, e, v, g=None):
    if a != "a" or e != "e" or v != "v":
        raise Exception(f"f9 Bad values")
    print(f"f9 received a next_node of {g}")

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

dialog_func_info = {f1:{}, f2:{}, f3:{}, f4:{}, f5:{}, f6:{}, f7:{},  f8:{}, f9:{}}
h = DialogHandler.DialogHandler()
simple_node = '''
id: One'''
loaded_node = NodeParser.parse_node(yaml.safe_load(simple_node))
active_node = BaseType.BaseNode(loaded_node)
h.register_functions(dialog_func_info)

def test_case1_order():
    assert h.format_parameters("f1", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e") == [active_node,"e"]
    assert h.format_parameters("f1", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e"]
    assert h.format_parameters("f1", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e"]
    assert h.format_parameters("f1", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e"]

def test_case2_order():
    assert h.format_parameters("f2", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e") == [active_node,"e",None]
    assert h.format_parameters("f2", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e","v"]
    assert h.format_parameters("f2", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e", None]
    assert h.format_parameters("f2", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","v"]

def test_case3_order():
    with pytest.raises(Exception):
        h.format_parameters("f3", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e")
    assert h.format_parameters("f3", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e","v"]
    with pytest.raises(Exception):
        h.format_parameters("f3", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g")
    assert h.format_parameters("f3", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","v"]

def test_case4_order():
    with pytest.raises(Exception):
        h.format_parameters("f4", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        h.format_parameters("f4", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    assert h.format_parameters("f4", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e","g"]
    assert h.format_parameters("f4", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","g"]

def test_case5_order():
    with pytest.raises(Exception):
        h.format_parameters("f5", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        h.format_parameters("f5", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    assert h.format_parameters("f5", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e","g", None]
    assert h.format_parameters("f5", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","g","v"]

def test_case6_order():
    with pytest.raises(Exception):
        h.format_parameters("f6", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        h.format_parameters("f6", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    with pytest.raises(Exception):
        h.format_parameters("f6", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g")
    assert h.format_parameters("f6", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","g","v"]

def test_case7_order():
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e") == [active_node,"e", None]
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e", None]
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e", None]
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e", None]
    with pytest.raises(Exception):
        h.format_parameters("f7", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        h.format_parameters("f7", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e","g"]
    assert h.format_parameters("f7", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","g"]

def test_case8_order():
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e") == [active_node,"e", None, None]
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e", None,"v"]
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e", None, None]
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e", None,"v"]
    with pytest.raises(Exception):
        assert h.format_parameters("f8", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        assert h.format_parameters("f8", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g") == [active_node,"e","g", None]
    assert h.format_parameters("f8", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","g","v"]

def test_case9_order():
    with pytest.raises(Exception):
        assert h.format_parameters("f9", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e")
    assert h.format_parameters("f9", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", values="v") == [active_node,"e","v", None]
    with pytest.raises(Exception):
        assert h.format_parameters("f9", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g")
    assert h.format_parameters("f9", POSSIBLE_PURPOSES.ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","v", None]
    with pytest.raises(Exception):
        assert h.format_parameters("f9", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e")
    with pytest.raises(Exception):
        assert h.format_parameters("f9", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", values="v")
    with pytest.raises(Exception):
        assert h.format_parameters("f9", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g")
    assert h.format_parameters("f9", POSSIBLE_PURPOSES.TRANSITION_ACTION, active_node=active_node, event="e", goal_node="g", values="v") == [active_node,"e","v","g"]