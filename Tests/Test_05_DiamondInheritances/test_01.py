import src.DialogNodeParsing as NodeParser
import ChildNode1 as CN1
import ChildNode2 as CN2
import GrandchildNode as GC

type_cache = {}

def test_register_all():
    NodeParser.register_node_type(CN1, "ChildOne", allowed_types=type_cache)
    NodeParser.register_node_type(CN2, "ChildTwo", allowed_types=type_cache)
    NodeParser.register_node_type(GC, "Grandchild", allowed_types=type_cache)
    assert len(type_cache) == 3

def test_parsed_fields():
    parsed_fields_one = [field["name"] for field in type_cache["ChildOne"].ChildOneGraphNode.PARSED_FIELDS]
    assert "CN1" in parsed_fields_one
    assert "CN2" not in parsed_fields_one
    assert "GC" not in parsed_fields_one
    parsed_fields_two = [field["name"] for field in type_cache["ChildTwo"].ChildTwoGraphNode.PARSED_FIELDS]
    assert "CN1" not in parsed_fields_two
    assert "CN2" in parsed_fields_two
    assert "GC" not in parsed_fields_two
    parsed_fields_three = [field["name"] for field in type_cache["Grandchild"].GrandchildGraphNode.PARSED_FIELDS]
    assert "CN1" in parsed_fields_three
    assert "CN2" in parsed_fields_three
    assert "GC" in parsed_fields_three

def test_schema():
    #Note: will need changes once de-duplication of schemas is added
    parsed_schema_one = type_cache["ChildOne"].ChildOneGraphNode.PARSED_SCHEMA
    assert len(parsed_schema_one["allOf"]) == 1
    parsed_schema_two = type_cache["ChildTwo"].ChildTwoGraphNode.PARSED_SCHEMA
    assert len(parsed_schema_two["allOf"]) == 1
    parsed_schema_three = type_cache["Grandchild"].GrandchildGraphNode.PARSED_SCHEMA
    assert len(parsed_schema_three["allOf"]) == 3

def test_node():
    node_data = {"type": "Grandchild", "id": "test"}
    node = NodeParser.parse_node(node_data, allowed_types=type_cache)
    assert isinstance(node, GC.GrandchildGraphNode)
    assert "CN1" in vars(node).keys()
    assert "CN2" in vars(node).keys()
    assert "GC" in vars(node).keys()