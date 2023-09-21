import ValidTestType as VT
import src.DialogNodeParsing as nodeParser
import pytest
import yaml

def test_invalid_passed_type():
    # covers not being able to find graph node of type. This time because wrong name passed in
    # technically also covers if graphnode has different name than the recorded type
    with pytest.raises(Exception):
        nodeParser.register_node_type(VT, "EIFJEIJF")

def test_invalid_modules():
    import InvalidType1 as ITT1 # Node is not a class
    import InvalidType2 as ITT2 # GraphNode is not a class
    import InvalidType3 as ITT3 # can't find a Node for the Type. This time because name mismatch
    import InvalidType4 as ITT4 # recorded type and type in class name don't match
    import InvalidType4 as ITT5 # bad version number. parsing tests has more thourough tests for string
    import InvalidType4 as ITT6 # root of definition wrong form
    import InvalidType4 as ITT7 # definition missing options key
    import InvalidType4 as ITT8 # definition Null options
    import InvalidType4 as ITT9 # option in definition badly formatted
    import InvalidType4 as ITT10 # inital look at schema shows invalid
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT1, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT2, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT3, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT4, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT5, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT6, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT7, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT8, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT9, "Test")
    with pytest.raises(Exception):
        nodeParser.register_node_type(ITT10, "Test")
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 1
        
def test_register():
    res = nodeParser.register_node_type(VT, "ValidTest")
    assert res == True
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2
    assert "ValidTest" in nodeParser.ALLOWED_NODE_TYPES
    res = nodeParser.register_node_type(VT, "ValidTest")
    assert res == False
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2

    # since registering types affects a global store, this continues with same types registered
    import ValidTestType2 as VT2
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT.ValidTestGraphNode.DEFINITION
    res = nodeParser.register_node_type(VT2, "ValidTest")
    assert res == False
    res = nodeParser.register_node_type(VT2, "ValidTest", re_register=True)
    assert res == True
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2
    assert "ValidTest" in nodeParser.ALLOWED_NODE_TYPES
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT2.ValidTestGraphNode.DEFINITION

    with pytest.raises(Exception):
        import InvalidType1 as ITT1 # Node is not a class
        nodeParser.register_node_type(ITT1, "Test")
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2

def test_load_type():
    nodeParser.register_node_type(VT, "ValidTest", re_register=True)
    nodeParser.load_type("ValidTest")
    assert len(nodeParser.NODE_DEFINITION_CACHE) == 2
    assert len(nodeParser.NODE_SCHEMA_CACHE) == 2
    assert nodeParser.NODE_DEFINITION_CACHE["ValidTest"] == yaml.safe_load(VT.ValidTestGraphNode.DEFINITION)

    with pytest.raises(Exception):
        nodeParser.load_type("asdf")

    nodeParser.empty_cache()
    assert len(nodeParser.NODE_DEFINITION_CACHE) == 0
    assert len(nodeParser.NODE_SCHEMA_CACHE) == 0
    nodeParser.load_type("Base")




    
#TODO: this test file needs update