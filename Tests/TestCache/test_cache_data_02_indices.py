import pytest
import src.utils.Cache as Cache
from datetime import datetime, timedelta

def test_collection_index():
    c = Cache.Cache(secondaryIndices=["val1", Cache.CollectionIndex("val3","val3")])
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "val3": [4,5]}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    c.delete("Two")
    assert len(c.data) == 1
    assert "One" in c.data
    assert c.secondary_indices["val1"].pointers == {3: set(["One"])}
    assert c.secondary_indices["val3"].pointers == {4: set(["One"]), 5: set(["One"])}

def test_collection_index_lists_cross():
    '''check collection index can be defined on collections and pirimitive types'''
    # technically can handle a mix of lists and not, but not likely needed
    c = Cache.Cache(secondaryIndices=[Cache.CollectionIndex("val1","val1")])
    results = c.add_all({"One": {"id": "One", "val1": [4,5]}, "Two": {"id": "Two", "val1": "asdf"}, "Three": {"id": "Three", "val1": set([4,2, "asdf"])}})

    assert c.secondary_indices["val1"].pointers == {"asdf":set(["Two", "Three"]), 4:set(["One", "Three"]), 5:set(["One"]),  2:set(["Three"])}

    c.delete("One")
    assert c.secondary_indices["val1"].pointers == {"asdf":set(["Two", "Three"]), 4:set(["Three"]),  2:set(["Three"])}
    c.delete("Two")
    assert c.secondary_indices["val1"].pointers == {"asdf":set(["Three"]), 4:set(["Three"]),  2:set(["Three"])}

def test_collection_index_dicts():
    '''check collection index can be defined on dictionaries too without breaking'''
    # honestly don't do this, just put it in the cache entry
    c = Cache.Cache(secondaryIndices=[Cache.CollectionIndex("val1","val1")])
    results = c.add_all({"One": {"id": "One", "val1": {"nest_key": "test", "test_key":[1,2,3]} }})

    assert c.secondary_indices["val1"].pointers == {"nest_key": set(["One"]), "test_key":set(["One"])}

    c.delete("One")
    assert c.secondary_indices["val1"].pointers == {}

def test_2():
    test = Cache.SimpleIndex("test", "test")
    test.add_pointer("pk","sk")
    test.del_pointer("pk", {})