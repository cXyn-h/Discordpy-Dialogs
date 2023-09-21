import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_parse_node_simple():
    simple_input='''
id: One'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))
    assert isinstance(loaded_node,BaseType.BaseGraphNode)
    assert loaded_node.id == "One"
    # assert no extra keys
    fields = yaml.safe_load(BaseType.BaseGraphNode.DEFINITION)["options"]
    for field in fields:
        assert hasattr(loaded_node, field["name"])
        if "default" in field:
            assert field["default"] == getattr(loaded_node, field["name"])

def test_parse_invalid_blank_id():
    simple_input='''
id:'''
    with pytest.raises(Exception):
        loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

def test_parse_invalid_no_id():
    simple_input='''
TTL: 300'''
    with pytest.raises(Exception):
        loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

#TODO: tests for all the other can't be empty fields?

def test_parse_file_simple_node():
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"

def test_parse_file_node_additions():
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list2.yml", parsed_nodes)
    assert len(parsed_nodes) == 3
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"

def test_parse_file_separated_parsed_lists():
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_file("Tests/TestParsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_parse_existing_excepts():
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"
    with pytest.raises(Exception):
        NodeParser.parse_file("Tests/TestParsing/node_list1.yml", parsed_nodes)

def test_parse_files_node_additions():
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_files("Tests/TestParsing/node_list2.yml", "Tests/TestParsing/node_list3.yml", existing_nodes=parsed_nodes)
    assert len(parsed_nodes) == 5
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"

def test_parse_files_separated_parsed_lists():
    parsed_nodes = NodeParser.parse_files("Tests/TestParsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_files("Tests/TestParsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_empty_cache_clears_only_caches():
    NodeParser.empty_cache()
    assert len(NodeParser.ALLOWED_NODE_TYPES) > 0
    assert len(NodeParser.NODE_DEFINITION_CACHE) == 0
    assert len(NodeParser.NODE_SCHEMA_CACHE) == 0

def test_version_string():
    assert NodeParser.parse_version_string("1.0.0") == (1,0,0)
    with pytest.raises(Exception):
        NodeParser.parse_version_string("asdf.4.5")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("4.$.5")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("4.6.5f")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("4.6.5.3")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("4.6")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("6")