import pytest
import src.utils.Cache as Cache

def test_set_item_non_existant():
    '''test trying to set an item that doesn't exist yet goes to add correctly'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    test_mi.set_item(5, {"A":"b", "B": [3,5]})
    assert 5 in test_mi
    assert test_mi.get(5)[0] == {"A":"b", "B": [3,5]}

def test_set_item_no_prev_keys():
    '''test set item gets right previous keys and sets data and indices correctly'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    test_mi.set_item(1, {"A": 1, "B": [6,3]})
    assert test_i.pointers[1] == set([1])
    assert test_i2.pointers[6] == set([1])
    assert 1 in test_i2.pointers[3]

def test_set_item_prev_keys():
    '''test cache takes previous keys and uses them'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    test_mi.set_item(2, {"A": 1, "B": [6,3]}, previous_secondary_keys={"first_test": [], "second_test": [1]})
    assert test_i.pointers[1] == set([2])
    assert 2 in test_i2.pointers[2]
    # In actual situation it should have been removed from above index
    assert test_i2.pointers[6] == set([2])
    assert 2 in test_i2.pointers[3]