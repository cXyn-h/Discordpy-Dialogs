import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import ValidTestType as VT

def test_find_Valid_Type():
    '''test the find_node_classes helper is able to correctly identify Base and the ValidTest type definition as valid'''
    assert ["Base"] == NodeParser.find_node_classes(BaseType)
    assert ["ValidTest"] == NodeParser.find_node_classes(VT)

def test_finding_invalids():
    '''test the find_node_classes helper doesn't find anything in parser class'''
    import InvalidType1 as ITT1 # Node is not a class
    import InvalidType2 as ITT2 # GraphNode is not a class
    import InvalidType3 as ITT3 # can't find a Node for the Type. This time because name mismatch
    import InvalidType4 as ITT4 # recorded type and type in class name don't match
    import InvalidType5 as ITT5 # bad version number. parsing tests has more thourough tests for string
    import InvalidType6 as ITT6 # root of definition wrong form
    import InvalidType7 as ITT7 # definition missing options key
    import InvalidType8 as ITT8 # definition Null options
    import InvalidType9 as ITT9 # option in definition badly formatted
    import InvalidType10 as ITT10 # inital look at schema shows invalid
    found_types = NodeParser.find_node_classes(ITT1)
    assert found_types == []
    found_types = NodeParser.find_node_classes(ITT2)
    assert found_types == []
    found_types = NodeParser.find_node_classes(ITT3)
    assert found_types == []
    found_types = NodeParser.find_node_classes(ITT4)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT5)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT6)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT7)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT8)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT9)
    assert found_types == ["Test"]
    found_types = NodeParser.find_node_classes(ITT10)
    assert found_types == ["Test"]

def test_empty_cache_clears_only_caches():
    '''make sure emptying only clears out caches not allowed types list'''
    NodeParser.empty_cache(NodeParser.ALLOWED_NODE_TYPES)
    assert len(NodeParser.ALLOWED_NODE_TYPES) > 0
    assert "CLASS_FIELDS" not in vars(BaseType.BaseGraphNode).keys()
    assert "PARSED_SCHEMA" not in vars(BaseType.BaseGraphNode).keys()