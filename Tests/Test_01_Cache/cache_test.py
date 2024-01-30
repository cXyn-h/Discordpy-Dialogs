import pytest
import src.utils.Cache as Cache
from datetime import datetime, timedelta

def test_blank_cache_init():
    '''make sure simplest cache gets data set up'''
    c = Cache.Cache()
    assert type(c.secondary_indices) is dict
    assert len(c.secondary_indices) == 0
    assert c.default_get_copy_rule == Cache.COPY_RULES.ORIGINAL
    assert type(c.data) is dict
    assert len(c.data) == 0
    assert c.default_timeout == 180

def test_init_index():
    '''test initializing an index sets data up'''
    # indices don't really care about name, but it does matter for a cache
    test_ind = Cache.SimpleIndex("primary", "test")
    assert test_ind.name == "primary"
    assert test_ind.col_name == "test"
    assert test_ind.cache is None
    assert test_ind.pointers == {}
    test_simple = Cache.SimpleIndex("test", "example")
    assert test_simple.name == "test"
    assert test_simple.cache is None
    assert test_simple.col_name == "example"
    assert test_simple.pointers == {}
    test_collection = Cache.CollectionIndex("test", "show")
    assert test_collection.name == "test"
    assert test_collection.cache is None
    assert test_collection.col_name == "show"
    assert test_collection.pointers == {}

def test_index_set_cache():
    '''testing index can set cache reference after init and index any data added to cache before index got set'''
    #  Note, this functionalty is for catchup if index is added later or otherwise needs to reset
    c = Cache.Cache(input_secondary_indices=["val1"])
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": [1,2]}, "Two": {"id": "Two", "val1": 3, "val2": [3,2]}})
    # this isn't complete setup of index, it doesn't get updates when entries are changed. done this way just to test functionality of set_cache
    index = Cache.SimpleIndex("val1","val1")
    assert index.cache is None
    assert len(index.pointers) == 0
    index.set_cache(c)
    assert index.cache is c
    assert index.pointers == {3: set(["One", "Two"])}

    index2 = Cache.CollectionIndex("val2","val2")
    assert index2.cache is None
    assert len(index2.pointers) == 0
    index2.set_cache(c)
    assert index2.cache is c
    assert index2.pointers == {1: set(["One"]), 2: set(["One", "Two"]), 3: set(["Two"])}

def test_init_cache_index_names():
    '''test initializing a cache given just names works. certain names should not be added to cache'''
    # invalid name should just be ignored, otherwise valid index created and resulting data changes
    c = Cache.Cache(input_secondary_indices=["primary"])
    assert len(c.secondary_indices) == 0
    c = Cache.Cache(input_secondary_indices=["test", "primary"])
    assert len(c.secondary_indices) == 1
    assert "test" in c.secondary_indices
    testind = c.secondary_indices["test"]
    assert type(testind) is Cache.SimpleIndex
    assert testind.name == "test"
    assert testind.col_name == "test"
    assert testind.cache is c
    assert len(testind.pointers) == 0
    # repeats should be ignored
    c = Cache.Cache(input_secondary_indices=["test", "test"])
    assert len(c.secondary_indices) == 1

def test_init_index_and_cache():
    '''test initializing index object and passing to cache initializating has valid results. certain index names should not be added to cache'''
    # make sure creating index beforehand and initializing alao has valid result
    test_create_ind = Cache.SimpleIndex("test2", "test2")
    assert test_create_ind.cache is None
    c = Cache.Cache(input_secondary_indices=[test_create_ind])
    assert test_create_ind.cache is c
    assert len(test_create_ind.pointers) == 0
    assert len(c.secondary_indices) == 1
    assert "test2" in c.secondary_indices

    # reserved name should not work
    test_create_ind_2 = Cache.SimpleIndex("primary", "val3")
    test_create_ind_3 = Cache.CollectionIndex("primary", "val4")
    assert test_create_ind_2.cache is None
    c2 = Cache.Cache(input_secondary_indices=[test_create_ind_2, test_create_ind_3])
    assert len(c2.secondary_indices) == 0

    # duplicates should be ignored
    test_create_ind2 = Cache.CollectionIndex("test2", "test2")
    test_create_ind3 = Cache.SimpleIndex("test2", "test2")
    c4 = Cache.Cache(input_secondary_indices=[test_create_ind2, test_create_ind3])
    assert len(c4.secondary_indices) == 1

def test_add_index():
    '''test adding indices after cache initialization link up and index existing data'''
    c = Cache.Cache()
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3": [4,5]}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert len(c.secondary_indices) == 0
    index = Cache.SimpleIndex("val1","val1")
    c.add_indices([index])
    assert len(c.secondary_indices) == 1
    assert c.secondary_indices["val1"] is index
    assert index.cache is c
    assert index.pointers == {3: set(["One","Two"])}
    # test adding indices that don't fit in cache doesn't change the cache
    index2 = Cache.SimpleIndex("primary","val1")
    index3 = Cache.CollectionIndex("primary","val3")
    index4 = Cache.SimpleIndex("val1","val2")
    c.add_indices([index2, index3, index4])
    assert len(c.secondary_indices) == 1
    assert index2.cache is None
    assert index3.cache is None
    assert index3.cache is None
    assert c.secondary_indices["val1"] is index
    index5 = Cache.CollectionIndex("val3", "val3")
    c.add_indices([index5])
    assert len(c.secondary_indices) == 2
    assert c.secondary_indices["val3"] is index5
    assert index5.cache is c
    assert index5.pointers == {4: set(["One"]), 5: set(['One'])}

    c.add_indices(["val1", "val2", "primary"])
    assert len(c.secondary_indices) == 3

def test_add_not_index():
    '''make sure some bogus data does not cause changes'''
    c = Cache.Cache(input_secondary_indices=[[1,2,3], 4, object()])
    assert len(c.secondary_indices) == 0

def test_get():
    '''test get from cache from different indices returns correct data'''
    c = Cache.Cache(input_secondary_indices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    # get by primary key that exists, should return single element list
    result = c.get("One", index_name="primary")
    assert len(result) == 1
    assert type(result[0]) is Cache.CacheEntry
    assert result[0].data["id"] == "One"
    # should get default value if getting by a primary key that doesn't exist in cache
    result = c.get("asdf", index_name="primary")
    assert result is None
    result = c.get("bogus", index_name="primary", default="N/A")
    assert result == "N/A"

    # get by secondary key that doesn't exist should also return default value
    result = c.get("asdf", index_name="asdf", default="not found")
    assert result == "not found"

    # get on secondary index
    result = c.get("b", index_name="val2", default=None)
    assert len(result) == 1
    assert type(result[0]) is Cache.CacheEntry
    assert result[0].data["id"] == "Two"

    result = c.get(3, index_name="val1", default=None)
    assert len(result) == 2
    assert type(result[0]) is Cache.CacheEntry
    assert type(result[1]) is Cache.CacheEntry
    id_list = [res.data["id"] for res in result]
    assert "Two" in id_list
    assert "One" in id_list

    # get on secondary index where key isn't present
    result = c.get("sadf", index_name="val2", default=None)
    assert result is None

def test_get_key():
    '''test getting the primary keys for what is indexed under different categories is correct'''
    c = Cache.Cache(input_secondary_indices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    # get by primary key that exists
    result = c.get_key("One", index_name="primary")
    assert len(result) == 1
    assert result[0] == "One"
    # get by primary key that isn't inside returns default value
    result = c.get_key("asdf", index_name="primary")
    assert result is None
    result = c.get_key("bogus", index_name="primary", default="N/A")
    assert result == "N/A"

    # get by secondary key that doesn't exist
    result = c.get_key("asdf", index_name="asdf", default="not found")
    assert result == "not found"

    # get on secondary index
    result = c.get_key("b", index_name="val2", default=None)
    assert len(result) == 1
    assert result[0] == "Two"

    result = c.get_key(3, index_name="val1", default=None)
    assert len(result) == 2
    assert "Two" in result
    assert "One" in result

    # get on secondary index where key isn't present
    result = c.get_key("sadf", index_name="val2", default=None)
    assert result is None

def test_get_copy_rules():
    '''test applying rules for how to copy data in get method'''
    c = Cache.Cache(input_secondary_indices=["val1", "val2"], defualt_get_copy_rule=Cache.COPY_RULES.DEEP)
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "obj": set()}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    # test default gets applied
    result = c.get("One", index_name="primary")[0]
    print(result)
    print(result.data)
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" not in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].remove(1)
    # test overridding copy rule in get to None
    result = c.get("One", index_name="primary", override_copy_rule=Cache.COPY_RULES.ORIGINAL)[0]
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 in c.data["One"].data["obj"]
    result.data["obj"].remove(1)
    # test overridding copy rule in get to Shallow
    result = c.get("One", index_name="primary", override_copy_rule=Cache.COPY_RULES.SHALLOW)[0]
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" not in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 in c.data["One"].data["obj"]
    result.data["obj"].remove(1)
    # probs should test Attmpt, but that requires finding something that can't be pickled and causes error so leave that to later
    result = c.get("a", index_name="val2")[0]
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" not in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].remove(1)
    
    result = c.get("a", index_name="val2", override_copy_rule=Cache.COPY_RULES.ORIGINAL)[0]
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 in c.data["One"].data["obj"]
    result.data["obj"].remove(1)

    result = c.get("a", index_name="val2", override_copy_rule=Cache.COPY_RULES.SHALLOW)[0]
    assert "asdf" not in c.data["One"].data
    result.data["asdf"] = "asdf"
    assert "asdf" not in c.data["One"].data
    del result.data["asdf"]
    assert 1 not in c.data["One"].data["obj"]
    result.data["obj"].add(1)
    assert 1 in c.data["One"].data["obj"]
    result.data["obj"].remove(1)

def test_clear():
    c = Cache.Cache(input_secondary_indices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    c.clear()
    assert len(c.data) == 0
    assert len(c.secondary_indices["val1"].pointers) == 0
    assert len(c.secondary_indices["val2"].pointers) == 0
