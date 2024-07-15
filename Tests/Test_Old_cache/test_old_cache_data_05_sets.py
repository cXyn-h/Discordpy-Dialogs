import pytest
import src.utils.Cache_old as Cache_old

def test_primary_key_set():
    '''test set updates data and indices upon first and second set on same primary key'''
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    entry = c.set("One", {"id": "One", "val1": 3, "val2": [1,2]}, index_name="primary")
    assert entry is not None
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {1: set(["One"]), 2: set(["One"])}

    # testing or_create false will prevent add
    entry = c.set("Two", {"id": "Two", "val1": 3, "val2": "a"}, index_name="primary", or_create=False)
    assert entry is None
    assert len(c.data) == 1
    assert "One" in c.data

    # testing setting again changes data
    entry = c.set("One", {"id": "One", "val2": [3,4]}, index_name="primary")
    assert entry is not None
    assert entry.data == c.data["One"].data
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.data["One"].data == {"id": "One", "val2": [3,4]}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {3: set(["One"]), 4: set(["One"])}

    # sanity check: test or_create doesn't affect set
    c.set("One", {"id": "One", "val1": 4, "val2": ["b"]}, index_name="primary", or_create=False)
    assert c.data["One"].data == {"id": "One", "val1": 4, "val2": ["b"]}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"b": set(["One"])}

def test_nonexistant_secondary_set():
    '''test trying to set on non existant key doesn't do anything'''
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    entry = c.set("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="asdf", or_create=False)
    assert entry is None
    assert len(c.data) == 0
    entry = c.set("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="asdf")
    assert entry is not None
    assert len(c.data) == 1
    assert entry.primary_key in c.data

def test_set_empty():
    '''test setting list to empty updates data and indices'''
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    entry = c.set("One", {"id": "One", "val1": 3, "val2": [5,"A"]}, index_name="primary")
    assert entry.data == {"id": "One", "val1": 3, "val2": [5,"A"]}
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"A": set(["One"]), 5: set(["One"])}

    # testing setting again changes data
    entry = c.set("One", {}, index_name="primary")
    assert entry is not None
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.data["One"].data == {}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}

def test_set_secondary_empty():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": [5,"A"]}, "Two": {"id": "Two", "val1": 16, "val2": [9,"A"]}})
    
    results = c.set(key="A", value={}, index_name="val2")
    assert len(results) == 2
    assert "One" in results
    assert "Two" in results
    assert len(c.data) == 2
    assert c.data["One"].data == {}
    assert c.data["Two"].data == {}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}

def test_set_secondary():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": [5,"A"]}, "Two": {"id": "Two", "val1": 16, "val2": [9,"A"]}})
    
    results = c.set(key="A", value={"val1": 4, "val2":["fd"]}, index_name="val2")
    assert len(results) == 2
    assert "One" in results
    assert "Two" in results
    assert len(c.data) == 2
    assert c.data["One"].data == {"val1": 4, "val2":["fd"]}
    assert c.data["Two"].data == {"val1": 4, "val2":["fd"]}
    assert c.secondary_indices["val1"].pointers == {4: set(["One","Two"])}
    assert c.secondary_indices["val2"].pointers == {"fd": set(["One","Two"])}
    # test set on secondary index can set multiple entries that meet
    result = c.set(4, {"vvv":"vvv"}, index_name="val1")
    assert len(result) == 2
    assert c.data["One"].data == {"vvv":"vvv"}
    assert c.data["Two"].data == {"vvv":"vvv"}
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}

def test_set_secondary_or_create():
    c = Cache_old.Cache(input_secondary_indices=["val1", Cache_old.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"val1": 4, "val2":["fd"]}, "Two": {"id": "Two", "val1": 16, "val2": [9,"A"]}})
    # make sure or_create doesn't break updates on secondary indices
    result = c.set(16, {"test": "asdf"}, index_name="val1", or_create=False)
    assert len(result) == 1
    assert "Two" in result
    assert result["Two"].data == c.data["Two"].data
    assert len(c.data) == 2
    assert c.data["One"].data == {"val1": 4, "val2":["fd"]}
    assert c.data["Two"].data == {"test": "asdf"}
    assert c.secondary_indices["val1"].pointers == {4: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {"fd": set(["One"])}

    # test find nothing in secondary keys and or_create is false results in no changes
    result = c.set("v", {"val1":4}, index_name="val2", or_create=False)
    assert result == {}
    assert len(c.data) == 2

    # test conditions for acutally meeting and adding on secondary index set call
    result = c.set("v", {"val1":4}, index_name="val2", or_create=True)
    assert len(result) == 1
    second_random_key = list(result.keys())[0]
    assert len(c.data) == 3
    assert c.data["One"].data == {"val1": 4, "val2":["fd"]}
    assert c.data["Two"].data == {"test": "asdf"}
    assert c.data[second_random_key].data == {"val1":4}
    assert c.secondary_indices["val1"].pointers == {4: set(["One", second_random_key])}
    assert c.secondary_indices["val2"].pointers == {"fd": set(["One"])}

def test_set_copy_rules():
    '''test copy rules for setting data'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    update_data = {"obj": set()}
    c.set("One", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.DEEP)
    update_data["obj"].add("b")
    assert "b" not in c.data["One"].data["obj"]
    update_data["obj"].remove("b")
    c.set("Two", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.SHALLOW)
    update_data["obj"].add("b")
    assert "b" in c.data["Two"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["Two"].data["obj"]
    update_data["test2"] = 1
    assert "test2" not in c.data["Two"].data
    del update_data["test2"]
    c.set("Three", update_data, index_name="primary", addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    update_data["obj"].add("b")
    assert "b" in c.data["Three"].data["obj"]
    update_data["obj"].remove("b")
    assert "b" not in c.data["Three"].data["obj"]
    update_data["test2"] = 1
    assert "test2" in c.data["Three"].data
    del update_data["test2"]
