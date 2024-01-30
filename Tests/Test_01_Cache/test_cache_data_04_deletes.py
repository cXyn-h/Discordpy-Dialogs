import pytest
import src.utils.Cache as Cache

def test_delete_primary():
    '''testing deleting primary key cleans up data and indices'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    entry = c.add("One", {"id": "One", "val1": 3, "val2": [1,2]})
    assert entry is not None
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {1: set(["One"]), 2: set(["One"])}

    c.delete("One")
    assert len(c.data) == 0
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}

def test_delete_nonexistant_primary():
    '''test deleting a primary key that isn't in cache doesn't change data'''
    # no data returned, no changes to data. just gotta make sure doesn't crash too
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    c.add("One", {"id": "One", "val1": 3, "val2": [1,2]})
    c.delete("sdfsd")
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {1: set(["One"]), 2: set(["One"])}


def test_delete_nonexistant_secondary():
    '''test deleting on secondary index that doesn't exist doesn't affect anything'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    c.add("One", {"id": "One", "val1": 3, "val2": [1,2]})
    c.delete("One", index_name="sdfsd")
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {1: set(["One"]), 2: set(["One"])}

def test_delete_secondary_list():
    '''test deleting secondary with multiple items under the key'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": [1,2]}, "Two": {"id": "Two", "val1": 5, "val2": [2, "A"]}})

    c.delete(2, index_name="val2")
    assert len(c.data) == 0
    assert c.secondary_indices["val1"].pointers == {}
    assert c.secondary_indices["val2"].pointers == {}

def test_delete_secondary():
    '''test deleting secondary with just one item under the key'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": [1,2]}, "Two": {"id": "Two", "val1": 5, "val2": [2, "A"]}})

    c.delete(3, index_name="val1")
    assert len(c.data) == 1
    assert "Two" in c.data
    assert c.secondary_indices["val1"].pointers == {5: set(["Two"])}
    assert c.secondary_indices["val2"].pointers == {2: set(["Two"]), "A": set(["Two"])}

def test_delete_secondary_miss():
    '''test deleting on secondary index but key is not in it'''
    c = Cache.Cache(input_secondary_indices=["val1", Cache.CollectionIndex("val2", "val2")])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": [1,2]}, "Two": {"id": "Two", "val1": 5, "val2": [2, "A"]}})

    c.delete(4, index_name="val1")
    assert len(c.data) == 2
    assert "Two" in c.data
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {5: set(["Two"]), 3: set(["One"])}
    assert c.secondary_indices["val2"].pointers == {2: set(["Two", "One"]), "A": set(["Two"]), 1: set(["One"])}
