import pytest
import src.utils.Cache as Cache
def test_multiindex_set_cache():
    '''test setting cache to another cache works'''
    test_mi = Cache.MultiIndexer()
    test_cache = Cache.Cache()
    set_result = test_mi.set_cache(test_cache)
    assert set_result
    assert test_mi.cache is test_cache
    assert test_mi.is_cache_obj

    test_mi = Cache.MultiIndexer()
    set_result = test_mi.set_cache({})
    assert set_result
    assert not test_mi.is_cache_obj

def test_multiindex_set_cache_null():
    '''test trying to set cache to null, which isn't allowed, should not change anything'''
    test_mi = Cache.MultiIndexer()
    test_cache = Cache.Cache()
    set_result = test_mi.set_cache(None)
    assert not set_result
    assert test_mi.cache is not test_cache

def test_multiindex_set_cache_reindexes():
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}

    test_mi.set_cache({"pk1": {"A": 1, "B": [1,2,3]}, "pk2": {"A": 1}, "pk3": {"B": [1,4]}, "pk4": {"A": 3}})
    assert test_i.pointers == {1: set(["pk1", "pk2"]), 3: set(["pk4"])}
    assert test_i2.pointers == {1: set(["pk1", "pk3"]), 2: set(["pk1"]), 3: set(["pk1"]), 4: set(["pk3"])}

def test_add_index_reindexes_new():
    '''make sure adding indices only new ones are reindexed'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}

    test_i3 = Cache.FieldValueIndex("third_test", keys_value_finder=lambda x: [x.get("C")] if x.get("C") else None)
    test_i3.pointers = {"A":set([1,2])}
    test_mi.add_indices(test_i3)

    assert len(test_i3.pointers) == 0
    assert len(test_i.pointers) != 0
    assert len(test_i2.pointers) != 0

def test_reindex_specific_indices():
    '''test reindex corrects only indices named'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}

    test_mi.reindex(index_names=["first_test"])
    assert len(test_i.pointers) == 0
    assert len(test_i2.pointers) != 0

def test_reindex_all_indices():
    '''test reindex corrects all indices'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}

    test_mi.reindex()
    assert len(test_i.pointers) == 0
    assert len(test_i2.pointers) == 0

def test_reindex_bad_names():
    '''test reindex filters out names that don't work for this multiIndexer'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}

    test_mi.reindex(index_names=["primary", "test"])
    assert len(test_i.pointers) != 0
    assert len(test_i2.pointers) != 0

def test_reindex_data():
    '''test reindex with indices and data stored has indices correctly reflecting data afterwards'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_i.pointers = {"A":set([1,2])}
    test_i2.pointers = {"B":set([2,5])}
    test_mi.cache.update({"pk1": {"A": 1, "B": [1,2,3]}, "pk2": {"A": 1}, "pk3": {"B": [1,4]}, "pk4": {"A": 3}})

    test_mi.reindex()
    assert test_i.pointers == {1: set(["pk1", "pk2"]), 3: set(["pk4"])}
    assert test_i2.pointers == {1: set(["pk1", "pk3"]), 2: set(["pk1"]), 3: set(["pk1"]), 4: set(["pk3"])}
    
def test_multiindex_remove_indices():
    '''test removing the named indices'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    assert len(test_mi.secondary_indices) == 2
    test_mi.remove_indices("first_test")
    assert len(test_mi.secondary_indices) == 1
    assert "first_test" not in test_mi.secondary_indices
    assert "second_test" in test_mi.secondary_indices

def test_multiindex_remove_index_not_present():
    '''test remove filters out indices named that don't work for this MultiIndexer'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))

    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    assert len(test_mi.secondary_indices) == 2
    test_mi.remove_indices("sdfsg")
    assert len(test_mi.secondary_indices) == 2
    assert "first_test" in test_mi.secondary_indices
    assert "second_test" in test_mi.secondary_indices

def test_check_length():
    '''test length check returns accurate'''
    test_mi = Cache.MultiIndexer()
    assert len(test_mi) == 0
    test_mi.cache.update({"pk1": 3})
    assert len(test_mi) == 1

    test_cache = Cache.Cache()
    test_mi = Cache.MultiIndexer(cache=test_cache)
    assert len(test_mi) == 0
    test_cache.add_item("pk1", 3)
    assert len(test_mi) == 1

def test_check_contains():
    '''test check key contains are accurate'''
    test_mi = Cache.MultiIndexer()
    test_mi.cache.update({"pk1": 3})
    assert "pk1" in test_mi
    assert "control" not in test_mi

    test_cache = Cache.Cache()
    test_mi = Cache.MultiIndexer(cache=test_cache)
    test_cache.add_item("pk1", 3)
    assert "pk1" in test_mi
    assert "control" not in test_mi

def test_get_item_keys():
    '''test can accurately get all things multiindexer would track for an item'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_mi.cache.update({"pk1": {"A": 1, "B": [1,2,3]}, "pk2": {"A": 1}, "pk3": {"B": [1, 4]}, "pk4": {"A": 3}})
    test_mi.reindex()

    assert test_mi.get_all_secondary_keys("pk1") == {"first_test": [1], "second_test": [1,2,3]}
    assert test_mi.get_all_secondary_keys("pk2") == {"first_test": [1], "second_test": []}
    assert test_mi.get_all_secondary_keys("pk3") == {"first_test": [], "second_test": [1,4]}

def test_get_item_keys_not_found():
    '''test trying to get secondary keys for an item that isn't recorded in multiindexer returns None'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])
    test_mi.cache.update({"pk1": {"A": 1, "B": [1,2,3]}, "pk2": {"A": 1}, "pk3": {"B": [1, 4]}, "pk4": {"A": 3}})
    test_mi.reindex()
    assert test_mi.get_all_secondary_keys("sdfsdf") is None