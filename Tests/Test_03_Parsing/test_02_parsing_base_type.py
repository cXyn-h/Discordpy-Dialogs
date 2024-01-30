import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_parse_node_simple():
    '''make sure loading a new node loads with all data'''
    simple_input='''
id: One'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))
    assert isinstance(loaded_node, BaseType.BaseGraphNode)
    assert loaded_node.TYPE == "Base"
    assert loaded_node.id == "One"
    # check all keys loaded in are as expected
    fields = BaseType.BaseGraphNode.get_node_fields()
    for field in fields:
        assert hasattr(loaded_node, field["name"])
        if "default" in field:
            assert field["default"] == getattr(loaded_node, field["name"])

def test_parse_node_read_TTL():
    '''make sure loading a new node loads all default data with overrides from file'''
    simple_input='''
id: One
TTL: 300'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))
    assert isinstance(loaded_node, BaseType.BaseGraphNode)
    assert loaded_node.TYPE == "Base"
    assert loaded_node.id == "One"
    # check all keys loaded in are as expected
    fields = BaseType.BaseGraphNode.get_node_fields()
    for field in fields:
        assert hasattr(loaded_node, field["name"])
        if field["name"] == "TTL":
            assert 300 == getattr(loaded_node, "TTL")
        elif "default" in field:
            assert field["default"] == getattr(loaded_node, field["name"])

def test_parse_node_distinct_defaults():
    '''sanity check loading multiple nodes does not cross memory'''
    simple_input_01='''
id: One'''
    simple_input_02='''
id: Two'''
    loaded_node_01 = NodeParser.parse_node(yaml.safe_load(simple_input_01))
    loaded_node_02 = NodeParser.parse_node(yaml.safe_load(simple_input_02))
    assert isinstance(loaded_node_01, BaseType.BaseGraphNode)
    assert loaded_node_01.TYPE == "Base"
    assert loaded_node_01.id == "One"
    assert isinstance(loaded_node_02, BaseType.BaseGraphNode)
    assert loaded_node_02.TYPE == "Base"
    assert loaded_node_02.id == "Two"
    loaded_node_01.actions.append("Dfsdf")
    assert loaded_node_02.actions == []
    loaded_node_01.events.update({"A":"a"})
    assert loaded_node_02.events == {}
    loaded_node_01.close_actions.append("Dfsdf")
    assert loaded_node_02.close_actions == []

def test_parse_invalid_blank_id():
    '''should error out because no value specified for id. required and not to schema'''
    simple_input='''
id:'''
    with pytest.raises(Exception):
        loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

def test_parse_invalid_no_id():
    '''should error out because no id specified. required and not to schema'''
    simple_input='''
TTL: 300'''
    with pytest.raises(Exception):
        loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

# maybe add more tests for data does not fit schema
