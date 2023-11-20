import ValidTestType as VT
import ValidTestType2 as VT2
import src.DialogNodeParsing as nodeParser
import pytest
import yaml

def test_invalid_passed_type():
    '''test registering errors out if name passed is different from what node actually lists, even if node is valid'''
    # covers not being able to find graph node of type. This time because wrong name passed in
    # technically also covers if graphnode has different name than the recorded type
    with pytest.raises(Exception):
        nodeParser.register_node_type(VT, "EIFJEIJF")

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
    assert "Test" not in nodeParser.ALLOWED_NODE_TYPES
        
def test_register():
    '''test registering nodes loads the right info'''
    # try registering a new valid type
    res = nodeParser.register_node_type(VT, "ValidTest")
    assert res == True
    # double checking registering a new node type doesn't immediately load the info
    assert "ValidTest" not in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" not in nodeParser.NODE_SCHEMA_CACHE
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2
    assert "ValidTest" in nodeParser.ALLOWED_NODE_TYPES
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT.ValidTestGraphNode.DEFINITION

def test_reregister():
    '''test re-registering node type only affects allowed node list when allowed to reregister'''
    # since registering types affects a global store, this continues with same types registered
    # try registering a type under same name, shouldn't allow overwrites by default
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT.ValidTestGraphNode.DEFINITION
    res = nodeParser.register_node_type(VT2, "ValidTest")
    assert res == False
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT.ValidTestGraphNode.DEFINITION
    
    # allow overwrites of loaded types, should see a difference in loaded info
    res = nodeParser.register_node_type(VT2, "ValidTest", re_register=True)
    assert res == True
    assert len(nodeParser.ALLOWED_NODE_TYPES) == 2
    assert "ValidTest" in nodeParser.ALLOWED_NODE_TYPES
    assert nodeParser.ALLOWED_NODE_TYPES["ValidTest"].ValidTestGraphNode.DEFINITION == VT2.ValidTestGraphNode.DEFINITION

def test_load_type():
    '''test registering and loading types clear out outdated cache and loads into cache'''
    # failed re-register shouldn't affect cache
    nodeParser.register_node_type(VT2, "ValidTest")
    assert "ValidTest" not in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" not in nodeParser.NODE_SCHEMA_CACHE

    nodeParser.register_node_type(VT2, "ValidTest", re_register=True)
    # double checking registering a new node type doesn't immediately load the info
    assert "ValidTest" not in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" not in nodeParser.NODE_SCHEMA_CACHE
    # load should work after registering
    nodeParser.load_type("ValidTest")
    assert "ValidTest" in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" in nodeParser.NODE_SCHEMA_CACHE
    print(nodeParser.NODE_DEFINITION_CACHE["ValidTest"])
    assert nodeParser.NODE_DEFINITION_CACHE["ValidTest"] == [{'name': 'id'}, {'name': 'graph_start', 'default': None}, {'name': 'TTL', 'default': 180}, {'name': 'actions', 'default': []}, {'name': 'events', 'default': {}}, {'default': [], 'name': 'close_actions'}, {'name': 'asdf'}]

    nodeParser.register_node_type(VT, "ValidTest", re_register=True)
    # re-registering a node that was there should remove from cache
    assert "ValidTest" not in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" not in nodeParser.NODE_SCHEMA_CACHE
    # loading should get the new version's info
    nodeParser.load_type("ValidTest")
    assert "ValidTest" in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" in nodeParser.NODE_SCHEMA_CACHE
    assert nodeParser.NODE_DEFINITION_CACHE["ValidTest"] == [{'name': 'id'}, {'name': 'graph_start', 'default': None}, {'name': 'TTL', 'default': 180}, {'name': 'actions', 'default': []}, {'name': 'events', 'default': {}}, {'default': [], 'name': 'close_actions'}]

    # both reset these tests and make sure empty works
    nodeParser.empty_cache()
    assert len(nodeParser.NODE_DEFINITION_CACHE) == 0
    assert len(nodeParser.NODE_SCHEMA_CACHE) == 0
    nodeParser.load_type("Base")
    assert "Base" in nodeParser.NODE_DEFINITION_CACHE
    assert "Base" in nodeParser.NODE_SCHEMA_CACHE

def test_load_invalid_type_errors():
    '''make sure invalid types do throw errors for loading'''
    with pytest.raises(Exception):
        # can't load something that isn't registered
        nodeParser.load_type("asdf")

def test_validate_node():
    '''make sure can use a different type node and version and they are picked up by validation'''
    simple_input='''
id: One
type: ValidTest
version: {v}'''.format(v=VT.ValidTestGraphNode.VERSION)
    nodeParser.empty_cache()
    assert len(nodeParser.NODE_DEFINITION_CACHE) == 0
    assert len(nodeParser.NODE_SCHEMA_CACHE) == 0
    nodeParser.load_type("Base")
    assert "ValidTest" not in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" not in nodeParser.NODE_SCHEMA_CACHE
    found_type = nodeParser.validate_yaml_node(yaml.safe_load(simple_input))
    assert found_type == "ValidTest"
    assert "ValidTest" in nodeParser.NODE_DEFINITION_CACHE
    assert "ValidTest" in nodeParser.NODE_SCHEMA_CACHE

def test_invalid_node():
    '''make sure validation errors if trying to use a type that isn't allowed'''
    simple_input='''
id: One
type: WRONG
version: {v}'''.format(v=VT.ValidTestGraphNode.VERSION)
    with pytest.raises(Exception):
        found_type = nodeParser.validate_yaml_node(yaml.safe_load(simple_input))

def test_node_definition():
    test2 = VT2.ValidTestGraphNode({})
    print(test2.get_node_fields())
    assert test2.get_node_fields() == [{'name': 'id'}, {'name': 'graph_start', 'default': None}, {'name': 'TTL', 'default': 180}, {'name': 'actions', 'default': []}, {'name': 'events', 'default': {}}, {'name': 'close_actions', 'default': []}, {'name': 'asdf'}]


#TODO: expand tests to cover more validation checks for node definitions, especially for schema, when that is fixed