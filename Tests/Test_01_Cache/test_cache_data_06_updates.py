import pytest
import src.utils.Cache_old as Cache_old
from datetime import datetime, timedelta

# tests for updates on CacheEntry objects. Just that type.

def test_update_primary():
    '''test updating on primary indices updates data and indices and or_create flag operates correctly'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    # testing or_create does add
    entry = c.update("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="primary")
    assert len(c.data) == 1
    assert "One" in c.data
    assert entry is c.data["One"]
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a"}

    # testing or_create false will prevent add
    entry = c.update("Two", {"id": "Two", "val1": 3, "val2": "a"}, index_name="primary", or_create=False)
    assert entry is None
    assert len(c.data) == 1
    assert "One" in c.data

    # update existing item test
    entry = c.update("One", {"id": "One", "val1": 4, "val2": "a", "test": "test"}, index_name="primary")
    assert entry is c.data["One"]
    assert c.data["One"].data == {"id": "One", "val1": 4, "val2": "a", "test": "test"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"])}
    # there is an attempt to change timeout but not very useful to test in synchnous execution
    # update existing item fewer fields
    entry = c.update("One", {"id": "One", "val1": 3}, index_name="primary")
    assert entry is c.data["One"]
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "test": "test"}
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"])}
    # sanity check: test or_create doesn't affect updates
    c.update("One", {"id": "One", "val1": 4, "val2": "b"}, index_name="primary", or_create=False)
    assert c.data["One"].data == {"id": "One", "val1": 4, "val2": "b", "test": "test"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"b": set(["One"])}

def test_update_nonexistant_secondary():
    '''test trying to update or create when trying to find items with a secondary index that doesn't exist'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    entry = c.update("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="primary")
    # test trying to update using nonexistant index allows create
    entry = c.update("One", {"id": "One", "val1": 1234, "val2": "cd"}, index_name="asdf")
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a"}
    assert entry.data == {"id": "One", "val1": 1234, "val2": "cd"}
    first_rand_key = entry.primary_key
    assert entry is c.data[entry.primary_key]
    assert len(c.data) == 2
    assert c.secondary_indices["val1"].pointers == {3: set(["One"]), 1234:set([first_rand_key])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"]), "cd":set([first_rand_key])}
    # test nonexistance index and not allowed to create
    entry = c.update("One", {"id": "One", "val1": 97, "val2": "fc"}, index_name="asdf", or_create=False)
    assert entry is None
    assert len(c.data) == 2
    assert c.secondary_indices["val1"].pointers == {3: set(["One"]), 1234:set([first_rand_key])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"]), "cd":set([first_rand_key])}

def test_update_seconadary():
    '''updates using find by secondary index'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    entry = c.update("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="primary")
    entry = c.update("Two", {"id": "Two", "val1": 3, "val2": "cd"}, index_name="primary")
    # test updates on secondary index
    result = c.update("cd", {"val1":3}, index_name="val2")
    assert "Two" in result
    assert len(result) == 1
    assert result["Two"].data == {"id": "Two", "val1": 3, "val2": "cd"}
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a"}
    assert c.data["Two"].data == {"id": "Two", "val1": 3, "val2": "cd"}
    assert c.secondary_indices["val1"].pointers == {3: set(["One", "Two"])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"]), "cd":set(["Two"])}

    # make sure or_create doesn't break updates on secondary indices
    result = c.update("cd", {"test": "asdf"}, index_name="val2", or_create=False)
    assert len(result) == 1
    assert "Two" in result
    assert result["Two"].data == c.data["Two"].data
    assert len(c.data) == 2
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a"}
    assert c.data["Two"].data == {"id": "Two", "val1": 3, "val2": "cd", "test": "asdf"}

    # test find nothing in secondary keys and or_create is false results in no changes
    result = c.update("v", {"val1":4}, index_name="val2", or_create=False)
    assert result == {}
    assert len(c.data) == 2

    # test conditions for acutally meeting and adding on secondary index update call
    result = c.update("v", {"val1":4}, index_name="val2", or_create=True)
    assert len(result) == 1
    second_random_key = list(result.keys())[0]
    assert len(c.data) == 3
    assert c.data[second_random_key].data == {"val1":4}
    assert c.secondary_indices["val1"].pointers == {3:set(["One", "Two"]), 4: set([second_random_key])}
    assert c.secondary_indices["val2"].pointers == {"a": set(["One"]), "cd":set(["Two"])}

    # test update on secondary index can update multiple entries that meet
    result = c.update(3, {"vvv":"vvv"}, index_name="val1")
    assert len(result) == 2
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "vvv":"vvv"}
    assert c.data["Two"].data == {"id": "Two", "val1": 3, "val2": "cd", "test": "asdf", "vvv":"vvv"}
    assert c.data[second_random_key].data == {"val1":4}

def test_update_copy_rule():
    '''test copy rules for updating data'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    update_data = {"obj": set()}
    c.update("One", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.DEEP)
    update_data["obj"].add("b")
    assert "b" not in c.data["One"].data["obj"]
    update_data["obj"].remove("b")
    c.update("Two", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.SHALLOW)
    update_data["obj"].add("b")
    assert "b" in c.data["Two"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["Two"].data["obj"]
    update_data["test2"] = 1
    assert "test2" not in c.data["Two"].data
    del update_data["test2"]
    c.update("Three", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    update_data["obj"].add("b")
    assert "b" in c.data["Three"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["Three"].data["obj"]
    update_data["test2"] = 1
    assert "test2" in c.data["Three"].data
    del update_data["test2"]

def test_update_strat_ADD():
    '''testing for strat that allows modifying lists inside a cache entry's data easier. 
    for lists, dicts and sets should add the pased in elements. for primitive types should be like a regular dict update and add/replace value'''

    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])


    c.update("One", {"val1": 1, "val2": ["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 1, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val1": None, "val2": None, "val3": None, "val4": None}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 1, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val1": 1, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 1, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    c.update("One", {"val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 1, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}

    c.update("One", {"val1": 4}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    c.update("One", {}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    c.update("One", {"val2": [{1,2}]}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D", {1,2}], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

def test_update_strat_SET():
    '''testing for strat that allows modifying lists inside a cache entry's data easier. 
    for lists, dicts and sets should set the whole thing to what was passed in. 
    for primitive types should be like a regular dict update and add/replace value'''

    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])

    c.update("One", {"val1": 1, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 1, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val1": 1, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 1, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}}
    assert c.secondary_indices["val2"].pointers == {"C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testb": set(["One"])}

    c.update("One", {"val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 1, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}, "val5": "asdf"}

    c.update("One", {"val1": 4}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 4, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testb": set(["One"])}

    c.update("One", {}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 4, "val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testb": set(["One"])}

def test_update_strat_DELETE():
    '''testing for strat that allows modifying lists inside a cache entry's data easier. 
    for lists, dicts and sets should delete the elements listed. for primitive types should delete the field'''

    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])

    c.update("One", {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    c.update("One", {"val2":["C", "D"], "val3": set([4]), "val4": {"testb": "B"}}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}

    c.update("One", {"val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B"], "val3": set([1,2,3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val1": None, "val3": [1,2]}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val2":["A", "B"], "val3": set([3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val2":["A", "B"], "val3": set([3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val2": [1, 2, 3], "val3": "F"}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val2":["A", "B"], "val3": set([3]), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

    c.update("One", {"val3": 3, "val2": None, "val4": [set([1,2])]}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {"val3": set(), "val4": {"testa": "A"}}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}
    assert c.secondary_indices["val3"].pointers == {}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"])}

def test_update_delete_fields():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])

    c.update("One", {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    c.update("One", {"val1": None, "val2": None, "val3": None, "val4": None, "val5": "dsfs"}, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}
    assert c.secondary_indices["val3"].pointers == {}
    assert c.secondary_indices["val4"].pointers == {}

def test_mix_copy_strat():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])

    c.update("One", {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.SET)

    cache_one_data = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]

    # test update with no changes doesn't affect anything when SET fields update mode
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert cache_one_data.data is c.data["One"].data
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    # test cache updates set fields strat with same object correct for string data
    del cache_one_data.data["val1"]
    assert c.data["One"].data == {"val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    assert cache_one_data.data is c.data["One"].data
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}

    # test cache updates set fields strat with same object correct for collections
    cache_one_data.data["val2"].remove("C")
    cache_one_data.data["val3"].remove(4)
    del cache_one_data.data["val4"]["testa"]
    assert c.data["One"].data == {"val2":["A", "B", "D"], "val3": set([1,2,3]), "val4": {"testb": "B"}, "val5": "asdf"}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "C": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"]), 4: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testa": set(["One"]), "testb": set(["One"])}
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val2":["A", "B", "D"], "val3": set([1,2,3]), "val4": {"testb": "B"}, "val5": "asdf"}
    assert cache_one_data.data is c.data["One"].data
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"]), "D": set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1: set(["One"]), 2: set(["One"]), 3: set(["One"])}
    assert c.secondary_indices["val4"].pointers == {"testb": set(["One"])}

    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.DELETE)
    assert c.data["One"].data == {'val2': [], 'val3': set(), 'val4': {}}
    assert cache_one_data.data is c.data["One"].data
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}
    assert c.secondary_indices["val3"].pointers == {}
    assert c.secondary_indices["val4"].pointers == {}

    cache_one_data.data.update({"val2": [], "val1": 1})
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert cache_one_data.data is c.data["One"].data
    assert c.data["One"].data == {"val1": 1, "val2":[], 'val3': set(), 'val4': {}}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {}

    cache_one_data.data.update({"val2": ["A","B"], "val1": 1})
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {}
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert cache_one_data.data is c.data["One"].data
    assert c.data["One"].data == {"val1": 1, "val2":["A","B"], 'val3': set(), 'val4': {}}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), "B": set(["One"])}

    # test weird situation. og data changed, but update won't change anything. indices should reflect og even if update doesn't do anything
    cache_one_data.data["val2"].remove("A")
    c.update("One", cache_one_data.data, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 1, "val2":["B"], 'val3': set(), 'val4': {}}
    assert c.secondary_indices["val1"].pointers == {1: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"B": set(["One"])}

def test_update_wrong_data_types():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2","val2"), Cache_old.CollectionIndex("val3","val3"), Cache_old.CollectionIndex("val4","val4")])

    c.update("One", {"val1": 4, "val2":["A", "B", "C", "D"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}, field_update_strat=Cache_old.UPDATE_STRAT.SET)

    c.update("One", {"val2":"Sdfsdf", "val3": [1,2,3,4], "val4": set(["testa", 1])}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D", "Sdfsdf"], "val3": set([1,2,3,4]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}
    
    c.update("One", {"val2":set([1,2]), "val3": ["A", "B"], "val4": 1}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val1": 4, "val2":["A", "B", "C", "D", "Sdfsdf", 1, 2], "val3": set([1,2,3,4, "A", "B"]), "val4": {"testa": "A", "testb": "B"}, "val5": "asdf"}

def test_nested_dict_update():
    # really recommended not to use nesting, just break the sections out into their own keys next to val2
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val2","val2")])

    c.update("One", {"val2": {"section1": {"testa": "A"}, "section2": {"testa": "a", "testb": "B"}}}, field_update_strat=Cache_old.UPDATE_STRAT.SET)
    assert c.data["One"].data == {"val2": {"section1": {"testa": "A"}, "section2": {"testa": "a", "testb": "B"}}}
    assert c.secondary_indices["val2"].pointers == {"section1": set(["One"]), "section2": set(["One"])}


    c.update("One", {"val2": {"section2": {"testc":"C"}}}, field_update_strat=Cache_old.UPDATE_STRAT.ADD)
    assert c.data["One"].data == {"val2": {"section1": {"testa": "A"}, "section2": {"testc": "C"}}}
    assert c.secondary_indices["val2"].pointers == {"section1": set(["One"]), "section2": set(["One"])}
    #TODO: test outputs here?