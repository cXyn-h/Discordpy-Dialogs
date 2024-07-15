import pytest
import copy
import src.utils.Cache as Cache

def test_get_keys_primary():
    '''test simple get keys for primary index'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys(1) == [1]

def test_get_key_primary_not_found():
    '''test simple get keys for primary index when key isn't there returns default value'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys(5) == None
    assert test_mi.get_keys(5, default="asdf") == "asdf"

def test_get_key_secondary_index_not_found():
    '''test getting on secondary index, but index not registered in multiindeixer'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys(5, index_name="dfsdg") == None
    assert test_mi.get_keys(5, index_name="dfsdg", default="asdf") == "asdf"

def test_get_key_secondary_index_items_not_found():
    '''test getting primary keys from a secondary index, but key not in secondary index'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys(5, index_name="first_test") == None
    assert test_mi.get_keys(5, index_name="first_test", default="asdf") == "asdf"

def test_get_key_secondary_index():
    '''test getting primary keys from a secondary index that finds keys'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys("a", index_name="first_test") == [1,3]

def test_get_keys_copy():
    '''tests that getting keys doesn't return a copy of index data so can't affect it'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    assert test_mi.get_keys("a", index_name="first_test") is not test_i.pointers["a"]

def test_get_primary_key():
    '''tests get function returns object when given a primary key'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get(1)
    assert len(result) == 1
    assert result[0] is test_mi.cache[1]

def test_get_primary_key_not_found():
    '''tests with secondary or primary keys if it is not found then return default value'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get(7)
    assert result is None
    assert test_mi.get(7, default="asdf") == "asdf"

def test_get_secondary_index_not_found():
    '''test getting on secondary index, but index not registered in multiindeixer'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get(7, index_name="dfsdf")
    assert result is None
    assert test_mi.get(7, index_name="dfsdf", default="asdf") == "asdf"

def test_get_secondary_key():
    '''tests get function returns object(s) when it finds stuff for a secondary key'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get("a", index_name="first_test")
    assert len(result) == 2
    assert result == [{"A": "a"}, {"A": "a", "B": [1,2]}]

def test_get_secondary_key_not_found():
    '''tests with secondary key if it is not found then return default value'''
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_mi = Cache.MultiIndexer(input_secondary_indices=[test_i, test_i2])

    results = test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get("g", index_name="first_test")
    assert result is None

def test_get_object_dict():
    '''test dictionary as cache returns the actual object. Expected to always return object stored, not copies'''
    test_mi = Cache.MultiIndexer()
    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})
    result = test_mi.get(1)

    test_mi.cache[1]["G"] = 2
    assert "G" in result[0]

def test_get_copy():
    '''test when given a cache that requires copies, get will return copies'''
    class CopyCache(Cache.Cache):
        def get(self, primary_key, default=None):
            return copy.deepcopy(super().get(primary_key, default))
        
    test_c = Cache.Cache()
    test_mi = Cache.MultiIndexer(cache=test_c)
    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})
    result = test_mi.get(1)
    test_mi.cache.data[1].update({"A": "a", "C": "c"})
    assert "C" in result[0]

    test_c = CopyCache()
    test_mi = Cache.MultiIndexer(cache=test_c)
    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get(1)
    test_mi.cache.data[1].update({"A": "a", "C": "c"})
    assert "C" not in result[0]

def test_get_copy_secondary_indices():
    '''test when cahce requires returning copies, getting by secondary index doesn't give originals'''
    class CopyCache(Cache.Cache):
        def get(self, primary_key, default=None):
            return copy.deepcopy(super().get(primary_key, default))
        
    test_i = Cache.FieldValueIndex("first_test", keys_value_finder=lambda x: [x.get("A")] if x.get("A") else None)
    test_i2 = Cache.FieldValueIndex("second_test", keys_value_finder=lambda x: x.get("B"))
    test_c = CopyCache()
    test_mi = Cache.MultiIndexer(cache=test_c, input_secondary_indices=[test_i, test_i2])

    data = {1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}}
    test_mi.add_items(data)

    result = test_mi.get("a", index_name="first_test")
    data[1].update({"A":1})
    data[3].update({"A":1})

    assert len(result) == 2
    assert result[0]["A"] == "a"
    assert result[1]["A"] == "a"

def test_get_ref_cache():
    '''test can get reference to item in cache'''
    class CopyCache(Cache.Cache):
        def get(self, primary_key, default=None):
            return copy.deepcopy(super().get(primary_key, default))
        
    test_c = CopyCache()
    test_mi = Cache.MultiIndexer(cache=test_c)
    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})

    result = test_mi.get_ref(1)
    test_mi.cache.data[1].update({"A": "a", "C": "c"})
    assert "C" in result

def test_get_ref_dict():
    '''test can get reference to item in dict storage'''
    test_mi = Cache.MultiIndexer()
    test_mi.add_items({1: {"A": "a"}, 2:{"B": [1,2]}, 3: {"A": "a", "B": [1,2]}, 4: {"A": "z", "B": [3,2]}})
    result = test_mi.get_ref(1)

    test_mi.cache[1]["G"] = 2
    assert "G" in result