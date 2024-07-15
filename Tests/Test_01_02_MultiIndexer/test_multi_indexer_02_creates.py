import pytest
import src.utils.Cache as Cache

def test_multiindex_simple_create():
    '''test creating multiIndexer on default values works'''
    test_mi = Cache.MultiIndexer()
    assert test_mi.cache == {}
    assert test_mi.secondary_indices == {}
    assert not test_mi.is_cache_obj

def test_multiindex_create_with_cache():
    '''test multiindexer picks up the right cache when it is passed in'''
    test_cache = Cache.Cache()
    test_mi = Cache.MultiIndexer(cache=test_cache)
    assert test_mi.cache is test_cache
    assert test_mi.secondary_indices == {}
    assert test_mi.is_cache_obj

def test_multiindex_create_with_dict():
    '''test multiIndexer picks up dict as storage when passed in'''
    test_cache = {}
    test_mi = Cache.MultiIndexer(cache=test_cache)
    assert test_mi.cache is test_cache
    assert test_mi.secondary_indices == {}
    assert not test_mi.is_cache_obj

    test_mi = Cache.MultiIndexer()
    assert test_mi.cache is not test_cache

def test_multiindex_create_with_indices():
    '''test multiIndexer stores indices when created with passed in index object'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    assert test_mi.secondary_indices.keys() == {"first_test", "second_test"}

def test_multiindex_create_invalid_indices():
    '''test multiIndexer rejects indices that don't work with with the rest of indices'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: x.get("B"))
    test_i3 = Cache.FieldValueIndex("primary", keys_value_finder=lambda x: x.get("B"))
    test_i4 = {}

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2, test_i3, test_i4])

    assert test_mi.secondary_indices.keys() == {"first_test"}
    assert test_mi.secondary_indices["first_test"] is test_i
    assert test_mi.secondary_indices["first_test"] is not test_i2

def test_multiindex_create_with_index_names():
    '''test default Index information gets created when initializing MultiIndexer'''
    test_mi = Cache.MultiIndexer(input_secondary_indices=["test"])

    assert test_mi.secondary_indices.keys() == {"test"}
    assert isinstance(test_mi.secondary_indices["test"], Cache.FieldValueIndex)
    assert test_mi.secondary_indices["test"].name == "test"

def test_multiindex_create_data_and_indices():
    '''test creating with data and indices present results in indices being up to date'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    cache = {"pk1": {"A": 1, "B": [1,2,3]}, "pk2": {"A": 1}, "pk3": {"B": [1,4]}, "pk4": {"A": 3}}
    test_mi = Cache.MultiIndexer(cache=cache, input_secondary_indices=[test_i, test_i2])
    assert test_i.pointers == {1: set(["pk1", "pk2"]), 3: set(["pk4"])}
    assert test_i2.pointers == {1: set(["pk1", "pk3"]), 2: set(["pk1"]), 3: set(["pk1"]), 4: set(["pk3"])}


