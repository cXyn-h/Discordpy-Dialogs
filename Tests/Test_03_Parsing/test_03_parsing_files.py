import src.DialogNodeParsing as NodeParser
import pytest

def test_parse_file_node_additions():
    '''make sure can call parse and add on nodes to existing list'''
    assert "Base" in NodeParser.ALLOWED_NODE_TYPES
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list2.yml", parsed_nodes)
    assert len(parsed_nodes) == 3
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"

def test_parse_file_separated_parsed_lists():
    '''sanity check that calling parse two separate times doesn't cross data'''
    assert "Base" in NodeParser.ALLOWED_NODE_TYPES
    # because default values only evaluated once, and existing nodes dict should have a default of empty 
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_file("Tests/Test_03_Parsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_parse_files_node_additions():
    '''make sure can parse mulitple files and it adds on nodes to existing list'''
    assert "Base" in NodeParser.ALLOWED_NODE_TYPES
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list1.yml")
    parsed_nodes = NodeParser.parse_files("Tests/Test_03_Parsing/node_list2.yml", "Tests/Test_03_Parsing/node_list3.yml", existing_nodes=parsed_nodes)
    assert len(parsed_nodes) == 5
    assert parsed_nodes["One"].id == "One"
    assert parsed_nodes["Two"].id == "Two"
    assert parsed_nodes["Three"].id == "Three"
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"

def test_parse_files_separated_parsed_lists():
    '''make sure calling parse_files multiple times does not cross data'''
    assert "Base" in NodeParser.ALLOWED_NODE_TYPES
    parsed_nodes = NodeParser.parse_files("Tests/Test_03_Parsing/node_list3.yml")
    parsed_nodes2 = NodeParser.parse_files("Tests/Test_03_Parsing/node_list2.yml")
    assert len(parsed_nodes) == 2
    assert parsed_nodes["Four"].id == "Four"
    assert parsed_nodes["Five"].id == "Five"
    assert len(parsed_nodes2) == 2
    assert parsed_nodes2["Two"].id == "Two"
    assert parsed_nodes2["Three"].id == "Three"

def test_parse_file_simple_node():
    '''make sure simple reading nodes from document doesn't break'''
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"

def test_parse_weird_docs():
    '''make sure weirdly formatted or empty docs don't cause errors'''
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list4.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["Seven"].id == "Seven"

def test_parse_existing_excepts():
    '''make sure it doesn't allow parsing node with same id again. make small thing apparent so it doesn't make things worse later'''
    parsed_nodes = NodeParser.parse_file("Tests/Test_03_Parsing/node_list1.yml")
    assert len(parsed_nodes) == 1
    assert parsed_nodes["One"].id == "One"
    with pytest.raises(Exception):
        NodeParser.parse_file("Tests/Test_03_Parsing/node_list1.yml", parsed_nodes)