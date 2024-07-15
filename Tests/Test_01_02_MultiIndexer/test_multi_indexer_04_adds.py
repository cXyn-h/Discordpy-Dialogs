import pytest
import src.utils.Cache as Cache

def test_add_new_item():
    '''test adding an item in cache that is not present in it yet'''
    test_mi = Cache.MultiIndexer()

    added_item = test_mi.add_item(1, {"A": "a"}, or_overwrite=False)
    assert added_item == 1

    assert len(test_mi) == 1
    assert 1 in test_mi

def test_add_new_item_indices():
    '''test adding an item with indices present that will record item'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    added_item = test_mi.add_item(1, {"A": "a"}, or_overwrite=False)
    assert added_item == 1

    assert len(test_mi) == 1
    assert 1 in test_mi
    assert test_i.pointers == {"a": set([1])}
    assert test_i2.pointers == {}

def test_add_existing_item_no_overwrite():
    '''test adding an item that already exists in cache but not allowing overwrites'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_mi.add_item(1, {"A": "a"}, or_overwrite=False)

    added_item = test_mi.add_item(1, {"A": "a"}, or_overwrite=False)
    assert added_item == None

    assert len(test_mi) == 1
    assert 1 in test_mi
    assert test_i.pointers == {"a": set([1])}
    assert test_i2.pointers == {}

def test_add_existing_item():
    '''test trying to add an existing item with overwrites allowed'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_mi.add_item(1, {"A": "a"}, or_overwrite=False)

    added_item = test_mi.add_item(1, {"A": "b"}, or_overwrite=True)
    assert added_item == 1

    assert len(test_mi) == 1
    assert 1 in test_mi
    assert test_i.pointers == {"b": set([1])}
    assert test_i2.pointers == {}

def test_add_new_item_cache():
    '''test adding item with cache class instead of dictionary'''
    test_cache = Cache.Cache()
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(cache=test_cache, input_secondary_indices=[test_i, test_i2])

    added_item = test_mi.add_item(1, {"A": "a"}, or_overwrite=False)
    assert added_item == 1

    assert len(test_mi) == 1
    assert 1 in test_mi
    assert test_i.pointers == {"a": set([1])}
    assert test_i2.pointers == {}

def test_add_items():
    '''test adding multile items'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A":"a"}, 2:{"B":[1,2]}})
    assert results == [1,2]

    assert len(test_mi) == 2
    assert 1 in test_mi
    assert 2 in test_mi
    assert test_i.pointers == {"a": set([1])}
    assert test_i2.pointers == {1: set([2]), 2: set([2])}

def test_add_items_no_overwrite():
    '''testing adding list with existing items with overwrites not allowed'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A":"a"}, 2:{"B":[1,2]}})

    results = test_mi.add_items({1: {"A":"a"}, 3:{"B":[1,2]}})
    assert results == [3]

def test_add_items_overwrites():
    '''testing adding list with existing items with overwrites allowed '''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A":"a"}, 2:{"B":[1,2]}})

    results = test_mi.add_items({1: {"A":"a"}, 3:{"B":[1,2]}}, or_overwrite=True)
    assert results == [1,3]

