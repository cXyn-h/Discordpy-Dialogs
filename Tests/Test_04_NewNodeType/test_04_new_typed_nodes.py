import ValidTestType as VT
import ValidTestType2 as VT2
import ValidTestType3 as VT3
import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import pytest
import yaml

def test_definition_merges():
    '''test function for finding graph node fields handles double definitions by merging them'''
    res = VT3.ValidTestGraphNode.get_node_fields()
    VT3.ValidTestGraphNode.CLASS_FIELDS[1].sort(key=lambda x: x["name"])
    res.sort(key=lambda x: x["name"])
    assert res == VT3.ValidTestGraphNode.CLASS_FIELDS[1]

def test_fields_merged():
    '''make sure node inheritance merges fields'''
    VT2.ValidTestGraphNode.clear_caches()
    VT2.ValidTestGraphNode.get_node_fields()
    parsed_field_names = [field["name"] for field in VT2.ValidTestGraphNode.CLASS_FIELDS[1]]
    assert len(parsed_field_names) > 1
    assert "testing" in parsed_field_names
    assert "id" in parsed_field_names
    VT2.ValidTestGraphNode.clear_caches()

def test_schema_merged():
    VT.ValidTestGraphNode.clear_caches()
    VT2.ValidTestGraphNode.clear_caches()
    VT2.ValidTestGraphNode.get_node_schema()
    assert len(VT2.ValidTestGraphNode.PARSED_SCHEMA[1]["allOf"]) == 2
    assert VT2.ValidTestGraphNode.PARSED_SCHEMA[1]["allOf"][0] == yaml.safe_load(VT2.ValidTestGraphNode.SCHEMA) or VT2.ValidTestGraphNode.PARSED_SCHEMA[1]["allOf"][1] == yaml.safe_load(VT2.ValidTestGraphNode.SCHEMA)
    VT2.ValidTestGraphNode.clear_caches()

def test_validate_node():
    '''make sure can use a different type node and version and they are picked up by validation'''
    simple_input='''
id: One
type: ValidTest
testing: HIHI
version: {v}'''.format(v=VT2.ValidTestGraphNode.get_version())
    type_cache = {}
    VT2.ValidTestGraphNode.clear_caches()
    res = NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    assert res == True
    assert "CLASS_FIELDS" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    
    found_type = NodeParser.validate_yaml_node(yaml.safe_load(simple_input), allowed_types=type_cache)
    assert found_type == "ValidTest"
    NodeParser.empty_cache(type_cache)

def test_fields():
    '''test built nodes gets fields from both child and parent classes'''
    type_cache = {}
    res = NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    test_node = NodeParser.parse_node({"type": "ValidTest", "id": "test", "testing": "asdf", "F": "F"}, allowed_types=type_cache)
    assert isinstance(test_node, VT2.ValidTestGraphNode)
    assert hasattr(test_node, "testing")
    assert hasattr(test_node, "id")
    assert not hasattr(test_node, "F")

    test_node = NodeParser.parse_node({"type": "Base", "id": "test2", "testing": "asdf", "F": "F"}, allowed_types=type_cache)
    assert isinstance(test_node, BaseType.BaseGraphNode)
    assert not hasattr(test_node, "testing")
    assert hasattr(test_node, "id")
    assert not hasattr(test_node, "F")

def test_missing_field():
    '''test building nodes errors out on fields introduced by new types in child nodes'''
    type_cache = {}
    res = NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    with pytest.raises(Exception):
        test_node = NodeParser.parse_node({"type": "ValidTest", "id": "test", "F": "F"}, allowed_types=type_cache)