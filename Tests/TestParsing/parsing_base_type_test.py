import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_parse_version_string():
    '''tests for validating version strings behaves as expected'''
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
    with pytest.raises(Exception):
        NodeParser.parse_version_string("-4.6.5")
    with pytest.raises(Exception):
        NodeParser.parse_version_string("4.-6.5")

def test_simple_valid_node():
    '''make sure validation for node definitions works on simple nodes'''
    simple_input='''
id: One'''
    NodeParser.validate_yaml_node(yaml.safe_load(simple_input))

def test_written_version():
    '''make sure validation for node definition picks up node version'''
    simple_input='''
id: One
v: {v}'''.format(v=NodeParser.ALLOWED_NODE_TYPES["Base"].BaseGraphNode.VERSION)
    NodeParser.validate_yaml_node(yaml.safe_load(simple_input))

def test_parse_node_simple():
    '''make sure loading a new node loads with all data'''
    simple_input='''
id: One'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))
    assert isinstance(loaded_node, BaseType.BaseGraphNode)
    assert loaded_node.id == "One"
    # check all keys loaded in are as expected
    fields = yaml.safe_load(BaseType.BaseGraphNode.DEFINITION)["options"]
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
    assert loaded_node.id == "One"
    # check all keys loaded in are as expected
    fields = yaml.safe_load(BaseType.BaseGraphNode.DEFINITION)["options"]
    for field in fields:
        assert hasattr(loaded_node, field["name"])
        if field["name"] == "TTL":
            assert 300 == getattr(loaded_node, "TTL")
        elif "default" in field:
            assert field["default"] == getattr(loaded_node, field["name"])

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

# #TODO: tests for all the other can't be empty fields?

def test_parse_file_simple_node():
    '''make sure simple reading nodes from document doesn't break'''
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"

def test_parse_weird_docs():
    '''make sure weirdly formatted or empty docs don't cause errors'''
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list4.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["Seven"].id == "Seven"

def test_parse_file_node_additions():
    '''make sure can call parse and add on nodes to existing list'''
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list2.yml", parsed_nodes)
    assert len(parsed_nodes) == 3
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"

def test_parse_file_separated_parsed_lists():
    '''sanity check that calling parse two separate times doesn't cross data'''
    # because default values only evaluated once, and existing nodes dict should have a default of empty 
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_file("Tests/TestParsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_parse_existing_excepts():
    '''make sure it doesn't allow parsing node with same id again. make small thing apparent so it doesn't make things worse later'''
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"
    with pytest.raises(Exception):
        NodeParser.parse_file("Tests/TestParsing/node_list1.yml", parsed_nodes)

def test_parse_files_node_additions():
    '''make sure can parse mulitple files and it adds on nodes to existing list'''
    parsed_nodes = NodeParser.parse_file("Tests/TestParsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_files("Tests/TestParsing/node_list2.yml", "Tests/TestParsing/node_list3.yml", existing_nodes=parsed_nodes)
    assert len(parsed_nodes) == 5
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"

def test_parse_files_separated_parsed_lists():
    '''make sure calling parse_files multiple times does not cross data'''
    parsed_nodes = NodeParser.parse_files("Tests/TestParsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_files("Tests/TestParsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_empty_cache_clears_only_caches():
    '''make sure emptying only clears out caches not allowed types list'''
    NodeParser.empty_cache()
    assert len(NodeParser.ALLOWED_NODE_TYPES) > 0
    assert len(NodeParser.NODE_DEFINITION_CACHE) == 0
    assert len(NodeParser.NODE_SCHEMA_CACHE) == 0
