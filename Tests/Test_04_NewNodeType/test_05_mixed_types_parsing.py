import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import ValidTestType2 as VT2

def test_parse_mixed_types():
    '''make sure can call parse and add on nodes to existing list'''
    type_cache = {}
    NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    NodeParser.register_node_type(BaseType, "Base", allowed_types=type_cache)
    parsed_nodes = NodeParser.parse_file("Tests/Test_04_NewNodeType/mixed_node_list_1.yaml", allowed_types=type_cache)
    assert len(parsed_nodes) == 2
    assert parsed_nodes["One"].id == "One"
    assert isinstance(parsed_nodes["One"], VT2.BaseType.BaseGraphNode)
    assert parsed_nodes["Two"].id == "Two"
    assert isinstance(parsed_nodes["Two"], VT2.ValidTestGraphNode)