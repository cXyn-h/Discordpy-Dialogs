import src.DialogNodeParsing as NodeParser
import src.DialogNodes.BaseType as BaseType
import ValidTestType as VT
import ValidTestType2 as VT2
import pytest

test_type_cache = {}

def test_invalid_passed_type():
    '''test registering errors out if name passed is different from what node actually lists, even if node is valid'''
    # covers not being able to find GraphNode of given type. This time because wrong name passed in
    # technically also covers if graphnode has different name than the recorded type
    with pytest.raises(Exception):
        NodeParser.register_node_type(VT, "EIFJEIJF", allowed_types={})

def test_register():
    '''test registering nodes loads the right info'''
    # try registering a new valid type
    type_cache = {}
    res = NodeParser.register_node_type(VT, "ValidTest", allowed_types=type_cache)
    assert res == True
    # double checking registering a new node type doesn't immediately load the info
    assert len(type_cache) == 1
    assert "ValidTest" in type_cache
    assert "CLASS_FIELDS" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert type_cache["ValidTest"].ValidTestGraphNode.ADDED_FIELDS == VT.ValidTestGraphNode.ADDED_FIELDS
    assert BaseType.BaseGraphNode.PARSED_SCHEMA[1] is not VT.ValidTestGraphNode.PARSED_SCHEMA[1]
    assert BaseType.BaseGraphNode.CLASS_FIELDS[1] is not VT.ValidTestGraphNode.CLASS_FIELDS[1]
    NodeParser.empty_cache(type_cache)

def test_reregister():
    '''test re-registering node type only affects allowed node list when allowed to reregister'''
    type_cache = {}
    res = NodeParser.register_node_type(VT, "ValidTest", allowed_types=type_cache)
    NodeParser.empty_cache(type_cache)
    assert res == True
    # try registering a type under same name, shouldn't allow overwrites by default
    assert type_cache["ValidTest"].ValidTestGraphNode.ADDED_FIELDS == VT.ValidTestGraphNode.ADDED_FIELDS
    VT2.ValidTestGraphNode.clear_caches()
    res = NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    assert res == False
    assert len(type_cache) == 1
    assert type_cache["ValidTest"].ValidTestGraphNode.ADDED_FIELDS == VT.ValidTestGraphNode.ADDED_FIELDS
    
    # allow overwrites of loaded types, should see a difference in loaded info
    VT2.ValidTestGraphNode.clear_caches()
    res = NodeParser.register_node_type(VT2, "ValidTest", re_register=True, allowed_types=type_cache)
    assert res == True
    assert len(type_cache) == 1
    assert "ValidTest" in type_cache
    assert type_cache["ValidTest"].ValidTestGraphNode.ADDED_FIELDS == VT2.ValidTestGraphNode.ADDED_FIELDS
    NodeParser.empty_cache(type_cache)


def test_invalid_modules():
    '''test trying to register invalid node types (could be for multitude reasions) does not happen'''
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
    type_cache = {}
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT1, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT2, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT3, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT4, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT5, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT6, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT7, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT8, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT9, "Test", allowed_types=type_cache)
    with pytest.raises(Exception):
        NodeParser.register_node_type(ITT10, "Test", allowed_types=type_cache)
    assert "Test" not in type_cache