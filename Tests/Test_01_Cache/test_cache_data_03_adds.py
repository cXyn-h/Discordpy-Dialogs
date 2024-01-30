import pytest
import src.utils.Cache as Cache
from datetime import datetime, timedelta

def test_add_data():
    '''test adding simple data entries to cache gets stored correctly'''
    c = Cache.Cache()
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a", "val3": [1,2]})
    assert result is not None
    # check cache was changed
    assert len(c.data) == 1
    assert "One" in c.data
    # make sure returned correct data - the entry that was just added
    entry = c.data["One"]
    assert result is entry
    # make sure what is stored is what was put in
    assert abs((entry.timeout - datetime.utcnow() - timedelta(seconds=180)).total_seconds()) < 0.5
    assert entry.data == {"id": "One", "val1": 3, "val2": "a", "val3": [1,2]}

def test_adding_empty_data():
    '''test adding weird data behaves ok and index on a field doesn't pick up empty'''
    c = Cache.Cache(input_secondary_indices=["val1"])
    result = c.add("One")

    assert result is not None
    # check cache was changed
    assert c.secondary_indices["val1"].pointers == {}
    assert len(c.data) == 1
    assert "One" in c.data
    # make sure returned correct data - the entry that was just added
    entry = c.data["One"]
    assert result is entry
    # make sure what is stored is what was put in
    assert abs((entry.timeout - datetime.utcnow() - timedelta(seconds=180)).total_seconds()) < 0.5
    assert len(entry.data) == 0

    result = c.add("One")
    assert result is None

    result = c.add("One", or_overwrite=True)
    assert result is not None
    assert "One" in c.data
    assert c.data["One"].data == {}

def test_add_data_indices():
    '''test indices are updating correctly in response to added simple data'''
    c = Cache.Cache(input_secondary_indices=["val1", "bogus", Cache.CollectionIndex("val3", "val3")])
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a", "val3": [1]})
    assert result is not None

    val1_ind = c.secondary_indices["val1"]
    assert val1_ind.pointers == {3: set(["One"])}

    bogus_ind = c.secondary_indices["bogus"]
    assert bogus_ind.pointers == {}

    val3_ind = c.secondary_indices["val3"]
    assert val3_ind.pointers == {1: set(["One"])}

    # secondary adds should not delete existing entries
    result = c.add("Two", {"id": "Two", "val1": 3, "val2": "b", "val3": [2]})
    assert result is not None
    val1_ind = c.secondary_indices["val1"]
    assert val1_ind.pointers == {3: set(["One", "Two"])}

    bogus_ind = c.secondary_indices["bogus"]
    assert bogus_ind.pointers == {}

    val3_ind = c.secondary_indices["val3"]
    assert val3_ind.pointers == {1: set(["One"]), 2: set(["Two"])}

    result = c.add("Three", {"id": "Three", "val1": 15, "val2": "b"})
    assert result is not None
    val1_ind = c.secondary_indices["val1"]
    assert val1_ind.pointers == {3: set(["One", "Two"]), 15: set(["Three"])}

    bogus_ind = c.secondary_indices["bogus"]
    assert bogus_ind.pointers == {}

    val3_ind = c.secondary_indices["val3"]
    assert val3_ind.pointers == {1: set(["One"]), 2: set(["Two"])}

def test_add_overwrite_flag():
    '''test adding data for same key and using overwrite flag behaves correctly and indices respond'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val3", "val3")])
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a", "val3": [1,2]})
    assert result is not None
    assert c.secondary_indices["val1"].pointers == {3:set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"])}

    result = c.add("One", {"id": "One", "val1": 5, "val2": "b"})
    assert result is None
    assert len(c.data["One"].data) == 4
    assert c.secondary_indices["val1"].pointers == {3:set(["One"])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"])}

    result = c.add("One", {"id": "One", "val1": 5, "val2": "b"}, or_overwrite=True)
    assert result is not None
    assert len(c.data) == 1
    assert len(c.data["One"].data) == 3
    entry = c.data["One"]
    assert result is entry
    assert abs((entry.timeout - datetime.utcnow() - timedelta(seconds=180)).total_seconds()) < 0.5
    assert entry.data == {"id": "One", "val1": 5, "val2": "b"}
    assert c.secondary_indices["val1"].pointers == {5:set(["One"])}
    assert c.secondary_indices["val3"].pointers == {}

def test_add_all():
    '''testing using the add multiple entries function updates data in cache correctly. uses same add as rest so assuming indices update as tested in test_add_data_indices'''
    # regular add all works
    c = Cache.Cache()
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert results["One"] is not None
    assert results["Two"] is not None
    assert len(c.data) == 2

    # add all with same key listed twice means last one overwrites the rest
    c = Cache.Cache()
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "One": {"id": "Two", "val1": 5, "val2": "b"}})
    assert len(results) == 1
    assert c.data["One"].data == {"id": "Two", "val1": 5, "val2": "b"}
    assert results["One"] is not None
    assert len(c.data) == 1

    # testing addall with some entries already present others not
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert len(results) == 2
    assert results["One"] is None
    assert results["Two"] is not None
    assert len(c.data) == 2

    # testing add all overwrite
    results = c.add_all({"One": {"id": "One", "val1": 6, "val2": "t"}, "Two": {"id": "Two", "val1": 16, "val2": "n"}}, or_overwrite=True)
    assert len(results) == 2
    assert results["One"] is not None
    assert c.data["One"].data == {"id": "One", "val1": 6, "val2": "t"}
    assert results["Two"] is not None
    assert c.data["Two"].data == {"id": "Two", "val1": 16, "val2": "n"}
    assert len(c.data) == 2

def test_add_copy_rule():
    '''testing the rules for how to copy data into the cache work'''
    c = Cache.Cache(input_secondary_indices=["val1", "val2"])
    update_data = {"obj": set("a")}
    c.add("Two", update_data, addition_copy_rule=Cache.COPY_RULES.DEEP)
    update_data["obj"].add("b")
    assert "b" not in c.data["Two"].data["obj"]
    update_data["obj"].remove("b")
    c.add("One", update_data, addition_copy_rule=Cache.COPY_RULES.SHALLOW)
    update_data["obj"].add("b")
    assert "b" in c.data["One"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["One"].data["obj"]
    update_data["test2"] = 3
    assert "test2" not in c.data["One"].data
    del update_data["test2"]
    c.add("Three", update_data, addition_copy_rule=Cache.COPY_RULES.ORIGINAL)
    update_data["obj"].add("b")
    assert "b" in c.data["Three"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["Three"].data["obj"]
    update_data["test2"] = 1
    assert "test2" in c.data["Three"].data
    del update_data["test2"]

def test_add_auto_key():
    c = Cache.Cache(input_secondary_indices=["val1", "val2"])
    result = c.add(value={"val1": 3, "val2": "a"})
    assert result is not None
    assert len(c.data) == 1
    key = list(c.data.keys())[0]
    assert {"val1": 3, "val2": "a"} == c.get(key, index_name="primary", override_copy_rule=Cache.COPY_RULES.ORIGINAL)[0].data
    assert c.secondary_indices["val1"].pointers == {3:set([key])}
    assert c.secondary_indices["val2"].pointers == {"a":set([key])}