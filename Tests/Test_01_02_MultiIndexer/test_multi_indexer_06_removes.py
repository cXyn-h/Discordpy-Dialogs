import pytest
import src.utils.Cache as Cache

def test_clear():
    ''' test calling clear on the multi indexer clears out all data'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    test_mi.clear()
    assert len(test_mi.cache) == 0
    assert len(test_i.pointers) == 0
    assert len(test_i2.pointers) == 0

def test_remove_item():
    ''' test can remove a primary key from storage and indices'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    data = {1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}}
    test_mi.add_items(data)

    item = data[1]
    result = test_mi.remove_item(1)
    assert 1 not in test_mi
    assert result is item
    assert 1 not in test_i.pointers["a"]

def test_remove_item_not_found():
    ''' test multiindexer doesn't break when trying to remove key that isn't there'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.remove_item(7)
    assert result is None

def test_remove_item_cache_object():
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_c = Cache.Cache()
    test_mi = Cache.MultiIndexer(cache=test_c, input_secondary_indices=[test_i, test_i2])

    data = {1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}}
    test_mi.add_items(data)

    item = data[1]
    result = test_mi.remove_item(1)
    assert 1 not in test_mi
    assert result is item
    assert 1 not in test_i.pointers["a"]