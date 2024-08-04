import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_clear_caches():
    '''test clear caches dumps cached data'''
    BaseType.BaseGraphNode.get_node_fields()
    BaseType.BaseGraphNode.get_node_schema()
    assert hasattr(BaseType.BaseGraphNode, "CLASS_FIELDS")
    assert hasattr(BaseType.BaseGraphNode, "PARSED_SCHEMA")
    BaseType.BaseGraphNode.clear_caches()
    assert not hasattr(BaseType.BaseGraphNode, "CLASS_FIELDS")
    assert not hasattr(BaseType.BaseGraphNode, "PARSED_SCHEMA")
