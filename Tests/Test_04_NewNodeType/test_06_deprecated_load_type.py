import src.DialogNodeParsing as NodeParser
import ValidTestType as VT
import ValidTestType2 as VT2
import pytest

# no longer works because NODE_FIELDS_CACHE, NODE_SCHEMA_CACHE, and load_type were removed

def deprecated_test_load_type():
    '''test registering and loading types clear out outdated cache and loads into cache'''
    type_cache = {}
    # failed re-register shouldn't affect cache
    NodeParser.register_node_type(VT2, "ValidTest", allowed_types=type_cache)
    assert "CLASS_FIELDS" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()

    NodeParser.register_node_type(VT2, "ValidTest", re_register=True, allowed_types=type_cache)
    # double checking registering a new node type doesn't immediately load the info
    assert "CLASS_FIELDS" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    # load should work after registering
    NodeParser.load_type("ValidTest", allowed_types=type_cache)
    assert "CLASS_FIELDS" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert type_cache["ValidTest"].ValidTestGraphNode.get_node_fields() == [{'name': 'id'}, {'name': 'graph_start', 'default': None}, {'name': 'TTL', 'default': 180}, {'name': 'actions', 'default': []}, {'name': 'events', 'default': {}}, {'default': [], 'name': 'close_actions'}, {'name': 'asdf'}]

    NodeParser.register_node_type(VT, "ValidTest", re_register=True, allowed_types=type_cache)
    # re-registering a node that was there should remove from cache
    assert "CLASS_FIELDS" not in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    assert "PARSED_SCHEMA" not in vars(type_cache["ValidTest"].ValidTestGraphNode).keys()
    # loading should get the new version's info
    NodeParser.load_type("ValidTest")
    assert "ValidTest" in NodeParser.NODE_FIELDS_CACHE
    assert "ValidTest" in NodeParser.NODE_SCHEMA_CACHE
    assert NodeParser.NODE_FIELDS_CACHE["ValidTest"] == [{'name': 'id'}, {'name': 'graph_start', 'default': None}, {'name': 'TTL', 'default': 180}, {'name': 'actions', 'default': []}, {'name': 'events', 'default': {}}, {'default': [], 'name': 'close_actions'}]

    # both reset these tests and make sure empty works
    NodeParser.empty_cache()
    assert len(NodeParser.NODE_FIELDS_CACHE) == 0
    assert len(NodeParser.NODE_SCHEMA_CACHE) == 0
    NodeParser.load_type("Base")
    assert "Base" in NodeParser.NODE_FIELDS_CACHE
    assert "Base" in NodeParser.NODE_SCHEMA_CACHE

def deprecated_test_load_unregistered_type_errors():
    '''make sure invalid types do throw errors for loading'''
    with pytest.raises(Exception):
        # can't load something that isn't registered
        NodeParser.load_type("asdf", allowed_types={})