import pytest
import Tests.Test_Old_cache.Cache_old as Cache_old

def test_reindex():
    '''test reindex updates indices when setting a value'''
    c = Cache_old.Cache(input_secondary_indices=["val1", "val2"])
    c.add("One", {"id": "One", "val1": 3, "val2": "a"})
    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val1"] = 4
    assert c.secondary_indices["val1"].pointers == {3:set(["One"])}
    assert entry.secondary_keys == {"val1": [3], "val2": ["a"]}
    print(entry.data)
    c.reindex(updated_keys="One")
    print(c.secondary_indices["val1"].pointers)
    assert c.secondary_indices["val1"].pointers == {4:set(["One"])}
    assert entry.secondary_keys == {"val1": [4], "val2": ["a"]}

def test_collection_reindex():
    '''test reindex updates collection index on adding another element to list'''
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add("One", {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])})
    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val3"].add(4)
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3,4])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"])}
    assert entry.secondary_keys["val3"] == [1,2,3]
    c.reindex(updated_keys="One")
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"]), 4:set(["One"])}
    assert entry.secondary_keys["val3"] == [1,2,3,4]

def test_collection_reindex_clear():
    '''test reindex clears indices when emptying data'''
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add("One", {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])})
    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val3"].clear()
    del entry.data["val2"]
    assert c.data["One"].data == {"id": "One", "val1": 3, "val3":set()}
    assert c.secondary_indices["val2"].pointers == {"a":set(["One"])}
    assert entry.secondary_keys["val2"] == ["a"]
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"])}
    assert entry.secondary_keys["val3"] == [1,2,3]
    c.reindex(updated_keys="One")
    assert c.secondary_indices["val3"].pointers == {}
    assert entry.secondary_keys["val3"] == []
    assert c.secondary_indices["val2"].pointers == {}
    assert entry.secondary_keys["val2"] == []

def test_reindex_all_entries():
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])}, "Two": {"id": "Two", "val1": 16, "val2": "b", "val3":set([5,6])}})
    assert c.secondary_indices["val2"].pointers == {"a":set(["One"]), "b":set(["Two"])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}
    c.data["One"].data["val3"] = set([1,2])
    c.data["Two"].data["val3"] = set([3])
    c.data["Two"].data["val2"] = 14
    del c.data["One"].data["val2"]
    assert c.data["One"].data == {"id": "One", "val1": 3, "val3":set([1,2])}
    assert c.data["Two"].data == {"id": "Two", "val1": 16, "val2": 14, "val3":set([3])}

    c.reindex()
    assert c.secondary_indices["val2"].pointers == {14:set(["Two"])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["Two"])}

def test_reindex_nonexistant_keys():
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])}, "Two": {"id": "Two", "val1": 16, "val2": "b", "val3":set([5,6])}})
    c.data["One"].data["val3"] = set([1,2])
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2])}

    c.reindex(updated_keys=["One", "Five"])
    assert c.secondary_indices["val2"].pointers == {"a":set(["One"]), "b":set(["Two"])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}

def test_update_catches_reindex():
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])}, "Two": {"id": "Two", "val1": 16, "val2": "b", "val3":set([5,6])}})

    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val3"].remove(3)
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}

    c.update("One", entry.data, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert id(entry.data) == id(c.data["One"].data)
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}


def test_set_catches_reindex():
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])}, "Two": {"id": "Two", "val1": 16, "val2": "b", "val3":set([5,6])}})

    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val3"].remove(3)
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}

    c.set("One", entry.data, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert id(entry.data) == id(c.data["One"].data)
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}

def test_add_catches_reindex():
    c = Cache_old.Cache(input_secondary_indices=[Cache_old.CollectionIndex("val3", "val3"), "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2,3])}, "Two": {"id": "Two", "val1": 16, "val2": "b", "val3":set([5,6])}})

    entry = c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0]
    entry.data["val3"].remove(3)
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2])}
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 3:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}

    c.add("One", entry.data, or_overwrite=True, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert c.data["One"].data == {"id": "One", "val1": 3, "val2": "a", "val3":set([1,2])}
    assert id(entry.data) == id(c.data["One"].data)
    assert c.secondary_indices["val3"].pointers == {1:set(["One"]), 2:set(["One"]), 5:set(["Two"]), 6:set(["Two"])}