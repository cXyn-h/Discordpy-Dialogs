import pytest
import src.utils.Cache as Cache
from datetime import datetime, timedelta

def test_blank_cache_init():
    c = Cache.Cache()
    assert type(c.secondary_indices) is dict
    assert len(c.secondary_indices) == 0
    assert c.default_get_copy_rule == Cache.COPY_RULES.ORIGINAL
    assert type(c.data) is dict
    assert len(c.data) == 0
    assert c.default_timeout == 180

def test_init_index():
    test_ind = Cache.Index("primary")
    assert test_ind.name == "primary"
    assert test_ind.cache is None
    assert test_ind.pointers == {}
    test_simple = Cache.SimpleIndex("test", "test")
    assert test_simple.name == "test"
    assert test_simple.cache is None
    assert test_simple.pointers == {}

def test_cache_indices():
    c = Cache.Cache(secondaryIndices=["primary"])
    assert len(c.secondary_indices) == 0
    c = Cache.Cache(secondaryIndices=["test", "primary"])
    assert len(c.secondary_indices) == 1
    assert "test" in c.secondary_indices
    testind = c.secondary_indices["test"]
    assert type(testind) is Cache.SimpleIndex
    assert testind.name == "test"
    assert testind.col_name == "test"
    assert testind.cache is c
    assert len(testind.pointers) == 0
    test_create_ind = Cache.SimpleIndex("test2", "test2")
    assert test_create_ind.cache is None
    c2 = Cache.Cache(secondaryIndices=[test_create_ind])
    assert test_create_ind.name == "test2"
    assert test_create_ind.col_name == "test2"
    assert test_create_ind.cache is c2
    assert len(test_create_ind.pointers) == 0
    assert len(c2.secondary_indices) == 1
    assert "test2" in c2.secondary_indices
    assert len(c.secondary_indices) == 1
    assert "test" in c.secondary_indices
    test_create_ind_2 = Cache.Index("primary")
    assert test_create_ind_2.name == "primary"
    assert test_create_ind_2.cache is None
    c3 = Cache.Cache(secondaryIndices=[test_create_ind_2])
    assert test_create_ind_2.cache is None
    assert len(c3.secondary_indices) == 0

def test_index_set_cache():
    #  Note, this functionalty is for catchup if index is added later or otherwise needs to reset
    c = Cache.Cache(secondaryIndices=["val1"])
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    # this isn't complete setup of index, it doesn't get updates when entries are changed. done this way just to test functionality of set_cache
    index = Cache.SimpleIndex("val1","val1")
    assert index.cache is None
    assert len(index.pointers) == 0
    index.set_cache(c)
    assert index.cache is c
    assert len(index.pointers) == 1
    assert 3 in index.pointers
    assert len(index.pointers[3]) == 2
    assert "One" in index.pointers[3]
    assert "Two" in index.pointers[3]


def test_add_data():
    c = Cache.Cache()
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a"})
    assert result is not None
    assert len(c.data) == 1
    assert "One" in c.data
    entry = c.data["One"]
    assert result is entry
    assert abs((entry.timeout - datetime.utcnow() - timedelta(seconds=180)).total_seconds()) < 0.5
    assert len(entry.data) == 3
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 3
    assert "val2" in entry.data
    assert entry.data["val2"] == "a"

def test_add_data_indices():
    c = Cache.Cache(secondaryIndices=["val1", "bogus"])
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a"})
    assert result is not None

    val1_ind = c.secondary_indices["val1"]
    assert len(val1_ind.pointers) == 1
    assert 3 in val1_ind.pointers
    assert len(val1_ind.pointers[3]) == 1
    assert "One" in val1_ind.pointers[3]

    bogus_ind = c.secondary_indices["bogus"]
    assert len(bogus_ind.pointers) == 0

    result = c.add("Two", {"id": "Two", "val1": 3, "val2": "b"})
    assert result is not None
    assert len(val1_ind.pointers) == 1
    assert 3 in val1_ind.pointers
    assert len(val1_ind.pointers[3]) == 2
    assert "One" in val1_ind.pointers[3]
    assert "Two" in val1_ind.pointers[3]

    bogus_ind = c.secondary_indices["bogus"]
    assert len(bogus_ind.pointers) == 0

    result = c.add("Three", {"id": "Three", "val1": 15, "val2": "b"})
    assert result is not None
    assert len(val1_ind.pointers) == 2
    assert 3 in val1_ind.pointers
    assert 15 in val1_ind.pointers
    assert len(val1_ind.pointers[3]) == 2
    assert "One" in val1_ind.pointers[3]
    assert "Two" in val1_ind.pointers[3]
    assert len(val1_ind.pointers[15]) == 1
    assert "Three" in val1_ind.pointers[15]

    bogus_ind = c.secondary_indices["bogus"]
    assert len(bogus_ind.pointers) == 0

def test_add_overwrite_flag():
    c = Cache.Cache()
    result = c.add("One", {"id": "One", "val1": 3, "val2": "a"})
    assert result is not None

    result = c.add("One", {"id": "One", "val1": 5, "val2": "b"})
    assert result is None
    assert len(c.data) == 1

    result = c.add("One", {"id": "One", "val1": 5, "val2": "b"}, or_overwrite=True)
    assert result is not None
    assert len(c.data) == 1
    entry = c.data["One"]
    assert result is entry
    assert abs((entry.timeout - datetime.utcnow() - timedelta(seconds=180)).total_seconds()) < 0.5
    assert len(entry.data) == 3
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 5
    assert "val2" in entry.data
    assert entry.data["val2"] == "b"

def test_add_all():
    # regular add all works
    c = Cache.Cache()
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert results["One"] is not None
    assert results["Two"] is not None
    assert len(c.data) == 2

    # add all with same entry kinda doues a collapse of same keys so that should work
    c = Cache.Cache()
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "One": {"id": "Two", "val1": 5, "val2": "b"}})
    assert len(results) == 1
    assert results["One"] is not None
    assert len(c.data) == 1

    # testing addall with some entries already present others not
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert len(results) == 2
    assert results["One"] is None
    assert results["Two"] is not None
    assert len(c.data) == 2

    # testing add all overwrite
    results = c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}}, or_overwrite=True)
    assert len(results) == 2
    assert results["One"] is not None
    assert results["Two"] is not None
    assert len(c.data) == 2

def test_add_copy_rule():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    update_data = {"obj": set("a")}
    c.add("One", update_data, addition_copy_rule=Cache.COPY_RULES.SHALLOW)
    assert update_data["obj"] is c.data["One"].data["obj"]
    c.add("Two", update_data, addition_copy_rule=Cache.COPY_RULES.DEEP)
    print(id(update_data["obj"]), id(c.data["Two"].data["obj"]))
    assert update_data["obj"] is not c.data["Two"].data["obj"]

def test_get():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    # get by primary key that exists
    result = c.get("One", index_name="primary")
    assert len(result) == 1
    assert type(result[0]) is not Cache.CacheEntry
    assert result[0]["id"] == "One"
    # get by primary key that isn't inside returns default value
    result = c.get("asdf", index_name="primary")
    assert result is None
    result = c.get("bogus", index_name="primary", default="N/A")
    assert result == "N/A"

    # get by secondary key that doesn't exist
    result = c.get("asdf", index_name="asdf", default="not found")
    assert result == "not found"

    # get on secondary index
    result = c.get("b", index_name="val2", default=None)
    assert len(result) == 1
    assert type(result[0]) is not Cache.CacheEntry
    assert result[0]["id"] == "Two"

    result = c.get(3, index_name="val1", default=None)
    assert len(result) == 2
    assert type(result[0]) is not Cache.CacheEntry
    assert type(result[1]) is not Cache.CacheEntry
    id_list = [res["id"] for res in result]
    assert "Two" in id_list
    assert "One" in id_list

    # get on secondary index where key isn't present
    result = c.get("sadf", index_name="val2", default=None)
    assert result is None

def test_get_key():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
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
    c = Cache.Cache(secondaryIndices=["val1", "val2"], defualt_get_copy_rule=Cache.COPY_RULES.DEEP)
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a", "obj": set()}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    result = c.get("One", index_name="primary")
    assert result[0] is not c.data["One"].data
    assert result[0]["obj"] is not c.data["One"].data["obj"]
    # test overridding copy rule in get to None
    result = c.get("One", index_name="primary", override_copy_rule=Cache.COPY_RULES.ORIGINAL)
    assert result[0] is c.data["One"].data
    assert result[0]["obj"] is c.data["One"].data["obj"]
    # test overridding copy rule in get to Shallow
    result = c.get("One", index_name="primary", override_copy_rule=Cache.COPY_RULES.SHALLOW)
    assert result[0] is not c.data["One"].data
    assert result[0]["obj"] is c.data["One"].data["obj"]
    # probs should test Attmpt, but that requires finding something that can't be pickled and causes error so leave that to later

def test_update():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    # testing or_create does add
    c.update("One", {"id": "One", "val1": 3, "val2": "a"},index_name="primary")
    assert len(c.data) == 1
    assert "One" in c.data
    # testing or_create prevents add
    c.update("Two", {"id": "Two", "val1": 3, "val2": "a"}, index_name="primary", or_create=False)
    assert len(c.data) == 1
    assert "One" in c.data

    # update existing item test
    c.update("One", {"id": "One", "val1": 4, "val2": "a", "test": "test"}, index_name="primary")
    entry = c.data["One"]
    assert len(entry.data) == 4
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 4
    assert "val2" in entry.data
    assert entry.data["val2"] == "a"
    assert "test" in entry.data

    # test nonexistant secondary index doesn't change anything
    c.update("One", {"id": "One", "val1": 1234, "val2": "cd"}, index_name="asdf")
    entry = c.data["One"]
    assert len(entry.data) == 4
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 4
    assert "val2" in entry.data
    assert entry.data["val2"] == "a"

    # actually add two now
    c.update("Two", {"id": "Two", "val1": 3, "val2": "a"}, index_name="primary")
    # test updating using secondary index
    c.update("a", {"testadd1": True}, index_name="val2")
    assert "testadd1" in c.data["One"].data
    assert "testadd1" in c.data["Two"].data

    c.update(3, {"testadd2": True}, index_name="val1")
    assert "testadd2" not in c.data["One"].data
    assert "testadd2" in c.data["Two"].data

def test_update_indices():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.update("One", {"id": "One", "val1": 3, "val2": "a"},index_name="primary")
    assert len(c.data) == 1
    assert "One" in c.data
    assert len(c.secondary_indices["val1"].pointers) == 1
    assert 3 in c.secondary_indices["val1"].pointers
    assert "One" in c.secondary_indices["val1"].pointers[3]
    c.update("One", {"id": "One", "val1": 4}, index_name="primary")
    assert len(c.secondary_indices["val1"].pointers) == 1
    assert 4 in c.secondary_indices["val1"].pointers
    assert 3 not in c.secondary_indices["val1"].pointers
    assert "One" in c.secondary_indices["val1"].pointers[4]
    c.update("One", {"id": "One", "test": "test"}, index_name="primary")
    assert len(c.secondary_indices["val1"].pointers) == 1
    assert 4 in c.secondary_indices["val1"].pointers
    assert 3 not in c.secondary_indices["val1"].pointers
    assert "One" in c.secondary_indices["val1"].pointers[4]
    assert len(c.secondary_indices["val2"].pointers) == 1
    assert "a" in c.secondary_indices["val2"].pointers
    assert "One" in c.secondary_indices["val2"].pointers["a"]

def test_update_copy_rule():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    update_data = {"obj": set()}
    c.update("One", update_data, index_name="primary", addition_copy_rule=Cache.COPY_RULES.SHALLOW)
    assert update_data["obj"] is c.data["One"].data["obj"]
    c.update("One", update_data, index_name="primary", addition_copy_rule=Cache.COPY_RULES.DEEP)
    assert update_data["obj"] is not c.data["One"].data["obj"]

def test_set():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.set("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="primary")
    assert len(c.data) == 1
    assert "One" in c.data

    # set existing item test
    c.set("One", {"id": "One", "val1": 4, "val2": "a", "test": "test"}, index_name="primary")
    entry = c.data["One"]
    assert len(c.data) == 1
    assert len(entry.data) == 4
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 4
    assert "val2" in entry.data
    assert entry.data["val2"] == "a"

    # test nonexistant secondary index doesn't change anything
    c.set("One", {"id": "One", "val1": 1234, "val2": "cd"}, index_name="asdf")
    entry = c.data["One"]
    assert len(entry.data) == 4
    assert "id" in entry.data
    assert entry.data["id"] == "One"
    assert "val1" in entry.data
    assert entry.data["val1"] == 4
    assert "val2" in entry.data
    assert entry.data["val2"] == "a"

    # actually add two now
    c.set("Two", {"id": "Two", "val1": 3, "val2": "a"})
    # test setting using secondary index
    c.set("a", {"testadd1": True}, index_name="val2")
    assert len(c.data["One"].data) == 1
    assert "testadd1" in c.data["One"].data
    assert len(c.data["Two"].data) == 1
    assert "testadd1" in c.data["Two"].data

    c.set("Two", {"id": "Two", "val1": 3, "val2": "a"},index_name="primary")

    c.set(3, {"testadd2": True}, index_name="val1")
    assert "testadd2" not in c.data["One"].data
    assert "testadd2" in c.data["Two"].data

def test_set_indicies():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.set("One", {"id": "One", "val1": 3, "val2": "a"}, index_name="primary")
    assert len(c.secondary_indices["val1"].pointers) == 1
    assert 3 in c.secondary_indices["val1"].pointers
    assert "One" in c.secondary_indices["val1"].pointers[3]
    c.set("One", {"id": "One"}, index_name="primary")
    assert len(c.secondary_indices["val1"].pointers) == 0
    assert len(c.secondary_indices["val2"].pointers) == 0

def test_set_copy_rules():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    update_data = {"obj": set()}
    c.set("One", update_data, index_name="primary", addition_copy_rule=Cache.COPY_RULES.SHALLOW)
    assert update_data["obj"] is c.data["One"].data["obj"]
    c.set("One", update_data, index_name="primary", addition_copy_rule=Cache.COPY_RULES.DEEP)
    assert update_data["obj"] is not c.data["One"].data["obj"]

def test_delete():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})

    c.delete("One", index_name="primary")
    assert len(c.data) == 1
    assert "One" not in c.data
    assert "Two" in c.data
    c.delete("One", index_name="primary")
    assert len(c.data) == 1

    c.delete("asdf", index_name="sdfasd")
    assert len(c.data) == 1
    assert "Two" in c.data

    c.add("One", {"id": "One", "val1": 3, "val2": "a"})
    c.delete(3, index_name="val1")
    assert len(c.data) == 0

    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    c.delete("a", index_name="val2")
    assert len(c.data) == 1
    assert "Two" in c.data

    c.delete("f", index_name="val2")
    assert len(c.data) == 1
    assert "Two" in c.data

def test_delete_indicies():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    assert len(c.secondary_indices["val2"].pointers) == 2
    c.delete("One", index_name="primary")
    assert len(c.secondary_indices["val1"].pointers) == 1
    assert len(c.secondary_indices["val2"].pointers) == 1
    assert 3 in c.secondary_indices["val1"].pointers
    assert "Two" in c.secondary_indices["val1"].pointers[3]
    assert "b" in c.secondary_indices["val2"].pointers
    assert "Two" in c.secondary_indices["val2"].pointers["b"]

def test_clear():
    c = Cache.Cache(secondaryIndices=["val1", "val2"])
    c.add_all({"One": {"id": "One", "val1": 3, "val2": "a"}, "Two": {"id": "Two", "val1": 3, "val2": "b"}})
    c.clear()
    assert len(c.data) == 0
    assert len(c.secondary_indices["val1"].pointers) == 0
    assert len(c.secondary_indices["val2"].pointers) == 0
