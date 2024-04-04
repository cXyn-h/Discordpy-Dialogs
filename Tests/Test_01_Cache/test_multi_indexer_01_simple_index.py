import pytest
import src.utils.Cache as CC
import src.DialogNodes.BaseType as BT

class IndexerCacheObject:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        pass

    def indexer(self, keys):
        if keys[0] == "done":
            return [], ["A", "B", "C"]
        if keys[0] == "few":
            first = keys.pop(0)
            return keys, self.few
        if keys[0] == "ignore":
            return None
        if keys[0] == "wrong":
            return keys, self
        
class dummyChacheobject:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        pass

def test_index_create():
    '''test simple index sets up all information it needs'''
    test_i = CC.FieldValueIndex("test", "test.i")
    assert test_i.pointers == {}
    assert test_i.name == "test"
    assert test_i.column_name == "test.i"

def test_1recur_index_get_keys_dict():
    test_i = CC.FieldValueIndex("test", "lvl1")
    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": ["A", "B"]}})
    assert keys == ["lvl2"]

    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": {"A":"a", "B":"b"}}})
    assert keys == ["lvl2"]

    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": "A"}})
    assert keys == ["lvl2"]

    keys = test_i.get_item_secondary_keys({"lvl1": "A"})
    assert keys == ["A"]

    keys = test_i.get_item_secondary_keys({"lvl1": ["A","B"]})
    assert keys.sort() == ["A", "B"].sort()

    keys = test_i.get_item_secondary_keys({"lvl2": ["A","B"]})
    assert keys == []

def test_2recur_index_get_keys_dict():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": ["A", "B"]}})
    assert keys.sort() == ["A", "B"].sort()

    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": {"A":"a", "B":"b"}}})
    assert keys.sort() == ["A", "B"].sort()

    keys = test_i.get_item_secondary_keys({"lvl1": {"lvl2": "A"}})
    assert keys == ["A"]

    keys = test_i.get_item_secondary_keys({"lvl1": "A"})
    assert keys == []

    keys = test_i.get_item_secondary_keys({"lvl1": ["A","B"]})
    assert keys == []

    keys = test_i.get_item_secondary_keys({"lvl2": ["A","B"]})
    assert keys == []

def test_index_get_keys_not_found():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    keys = test_i.get_item_secondary_keys({"lvl1": "A"})
    assert keys == []

    keys = test_i.get_item_secondary_keys({"asdf": "A"})
    assert keys == []

def test_1recur_index_get_keys_object():
    test_i = CC.FieldValueIndex("test", "lvl1")
    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl2="asd"))
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1="asd"))
    assert keys == ["asd"]

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=["A","B"]))
    assert keys.sort() == ["A", "B"].sort()

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(lvl2 = ["A", "B"])))
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(lvl2 = "A")))
    assert keys == []

def test_2recur_index_get_keys_object():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    keys = test_i.get_item_secondary_keys(dummyChacheobject())
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1="asd"))
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl2="asd"))
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=["A","B"]))
    assert keys == []

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(lvl2 = ["A", "B"])))
    assert keys.sort() == ["A", "B"].sort()

    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(A = ["A", "B"])))
    assert keys == []

def test_1recur_index_get_kets_indexer():
    # test indexer not handling key doesn't cause infinite loop and it goes to default handling mode
    test_i = CC.FieldValueIndex("test", "bogus.lvl2")
    keys = test_i.get_item_secondary_keys(IndexerCacheObject())
    assert keys == []

    keys = test_i.get_item_secondary_keys(IndexerCacheObject(bogus = "A"))
    assert keys == []

    keys = test_i.get_item_secondary_keys(IndexerCacheObject(bogus = {"lvl2":"a"}))
    assert keys == ["a"]

    test_i2 = CC.FieldValueIndex("test", "done")
    keys = test_i2.get_item_secondary_keys(IndexerCacheObject())
    assert keys.sort() == ["A","B","C"].sort()

    test_i3 = CC.FieldValueIndex("test", "few.test")
    keys = test_i3.get_item_secondary_keys(IndexerCacheObject(few = {"test": "A"}))
    assert keys == ["A"]

    keys = test_i3.get_item_secondary_keys(IndexerCacheObject(few = {"Sdfsd": "A"}))
    assert keys == []

    # make sure returning same object doesn't cause infinite loop
    test_i2 = CC.FieldValueIndex("test", "wrong")
    keys = test_i2.get_item_secondary_keys(IndexerCacheObject())
    assert keys == []

def test_index_add():
    test_i = CC.FieldValueIndex("test", "A")
    test_i.add_item(1, {"A": "a"})
    assert test_i.pointers == {"a": {1}}
    test_i.add_item(2, {"A": "a"})
    assert test_i.pointers == {"a": {1, 2}}
    test_i.add_item(3, {"A": "z"})
    assert test_i.pointers == {"a": {1, 2}, "z": {3}}

def test_index_nested_add():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    test_i.add_item(1, {"lvl1": {"lvl2": "a"}})
    assert test_i.pointers == {"a": {1}}
    test_i.add_item(2, {"lvl1": {"lvl2": ["z", "c"]}})
    assert test_i.pointers == {"a": {1}, "z":{2}, "c":{2}}
    test_i.add_item(3, {"lvl1": {"lvl2": "a"}})
    assert test_i.pointers == {"a": {1, 3}, "z":{2}, "c":{2}}

def test_index_get():
    test_i = CC.FieldValueIndex("test", "test")
    test_i.pointers = {"A":{1, 2}, "B": {3}, "C":{1, 3}}
    retrieved = test_i.get("A")
    assert retrieved == {1, 2}
    retrieved.add(6)
    assert 6 not in test_i.pointers["A"]

def test_index_clear():
    test_i = CC.FieldValueIndex("test", "test")
    test_i.pointers = {"A":{1, 2}, "B": {3}, "C":{1, 3}}
    test_i.clear()
    assert len(test_i.pointers) == 0

def test_index_remove_item():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    test_i.add_item(1, {"lvl1": {"lvl2": "a"}})
    assert test_i.pointers == {"a": {1}}
    test_i.add_item(2, {"lvl1": {"lvl2": ["z", "c"]}})
    assert test_i.pointers == {"a": {1}, "z":{2}, "c":{2}}
    test_i.add_item(3, {"lvl1": {"lvl2": "a"}})
    assert test_i.pointers == {"a": {1, 3}, "z":{2}, "c":{2}}
    test_i.remove_item(3, {"lvl1": {"lvl2": "a"}})
    assert test_i.pointers == {"a": {1}, "z":{2}, "c":{2}}
    test_i.remove_item(2, {"lvl1": {"lvl2": ["z", "c"]}})
    assert test_i.pointers == {"a": {1}}

def test_index_set_item():
    test_i = CC.FieldValueIndex("test", "lvl1.lvl2")
    test_i.add_item(1, {"lvl1": {"lvl2": "a"}})
    test_i.add_item(2, {"lvl1": {"lvl2": ["z", "c"]}})
    test_i._set_item_data(1, {"lvl1": {"lvl2": "a"}}, {"lvl1": {"lvl2": ["z", "c"]}})
    assert test_i.pointers == {"z":{1, 2}, "c":{1, 2}}

def test_subset():
    test_i = CC.ObjContainsFieldIndex("test", "lvl1.lvl2")
    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(lvl2 = ["A", "B"])))
    assert keys == ["does"]

    test_i = CC.ObjContainsFieldIndex("test", "lvl1")
    keys = test_i.get_item_secondary_keys(dummyChacheobject(lvl1=dummyChacheobject(lvl2 = ["A", "B"])))
    assert keys == ["does"]

    keys = test_i.get_item_secondary_keys(dummyChacheobject(v=dummyChacheobject(lvl2 = ["A", "B"])))
    assert keys == ["not"]

