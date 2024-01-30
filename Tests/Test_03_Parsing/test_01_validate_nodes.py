import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_simple_valid_node():
    '''make sure validation for node definitions works on simple nodes'''
    simple_input='''
id: One'''
    found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input))
    assert found_type == "Base"

def test_simple_valid_base_not_registered():
    '''Base type should always be avaiable but fixable if not there so make sure validate can compensate'''
    type_cache = {}
    simple_input='''
id: One'''
    found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input), allowed_types=type_cache)
    assert found_type == "Base"
    assert len(type_cache) == 1
    assert "Base" in type_cache

def test_simple_valid_node_declares_type():
    '''make sure validation for node definitions able to find type defined in node'''
    simple_input='''
id: One
type: Base'''
    found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input))
    assert found_type == "Base"

def test_simple_node_invalid_type():
    '''make sure validation for node definitions returns invalid when type isn't registered'''
    simple_input='''
id: One
type: asdf'''
    with pytest.raises(Exception):
        found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input))

def test_simple_node_version():
    '''make sure validation for node definition picks up node version'''
    simple_input='''
id: One
type: Base
version: {v}'''.format(v=BaseType.BaseGraphNode.get_version())
    found_type =NodeParser.validate_yaml_node(yaml.safe_load(simple_input))
    assert found_type == "Base"

def test_simple_node_v():
    '''make sure validation for node definition picks up node version, simple key version'''
    simple_input='''
id: One
type: Base
version: {v}'''.format(v=BaseType.BaseGraphNode.get_version())
    found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input))
    assert found_type == "Base"
    
def test_not_compatible():
    '''test the validator raises error when node definition has invalid version. This one specifically due to version string not being valid for base type'''
    simple_input='''
id: One
type: Base
version: {v}'''.format(v="a")
    with pytest.raises(Exception):
        found_type =NodeParser.validate_yaml_node(yaml.safe_load(simple_input))

def test_not_to_schema():
    '''test the validator raises error when node definition does not match schema'''
    simple_input='''
id: One
type: Base
graph_start: asdf'''
    with pytest.raises(Exception):
        found_type =NodeParser.validate_yaml_node(yaml.safe_load(simple_input))