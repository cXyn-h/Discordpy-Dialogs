import pytest
import src.utils.Cache as CC
import src.DialogNodes.BaseType as BT
from datetime import timedelta

def test_index_get_keys_nodes():
    node = BT.BaseGraphNode({"id": "One", "actions": ["funcA", "funcB", {"funcA": "parem"}]})
    test_i = CC.FieldValueIndex("test", "id")
    keys = test_i.get_item_secondary_keys(node)
    assert keys == ["One"]

    test_i2 = CC.FieldValueIndex("test", "node.id")
    keys = test_i2.get_item_secondary_keys({"node":node, "others":[]})
    assert keys == ["One"]

    test_i3 = CC.FieldValueIndex("test", "node.class")
    keys = test_i3.get_item_secondary_keys({"node":node, "others":[]})
    assert keys == ["BaseGraphNode"]

    test_i4 = CC.FieldValueIndex("test", "TYPE")
    keys = test_i4.get_item_secondary_keys(node)
    assert keys == ["Base"]

def test_index_get_node_actions():
    node = BT.BaseGraphNode({"id": "One", "actions": ["funcA", "funcB", {"funcA": "parem"}], "filters": ["funcC"]})
    test_i5 = CC.FieldValueIndex("test", "functions")
    keys = test_i5.get_item_secondary_keys(node)
    print(keys)
    assert keys.sort() == ["funcA", "funcB", "funcC"].sort()

    test_i2 = CC.FieldValueIndex("test", "node.functions")
    keys = test_i2.get_item_secondary_keys({"node":node})
    assert keys.sort() == ["funcA", "funcB", "funcC"].sort()

def test_index_get_keys_nodes_invalid():
    node = BT.BaseGraphNode({"id": "One"})
    test_i = CC.FieldValueIndex("test", "node")
    keys = test_i.get_item_secondary_keys({"node":node, "others":[]})
    assert keys == []

    test_i3 = CC.FieldValueIndex("test", "bogus")
    keys = test_i3.get_item_secondary_keys(node)
    assert keys == []

def test():
    test_mi = CC.MultiIndexer()
    node_one = BT.BaseGraphNode({"id": "One"})
    test_mi.add_item("One", node_one)
    node = test_mi.get_ref("One")
    assert node is node_one
    node_one.set_TTL(timeout_duration=timedelta(seconds=200))
    assert node.TTL == node_one.TTL