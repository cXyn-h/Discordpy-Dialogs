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
    key_value_finder = lambda x: x.i
    test_i = CC.FieldValueIndex("test", keys_value_finder=key_value_finder)
    assert test_i.pointers == {}
    assert test_i.name == "test"
    assert test_i.keys_value_finder is key_value_finder
    key_value_finder2 = lambda x: x.t
    test_i = CC.ObjContainsFieldIndex("test2", keys_value_finder=key_value_finder2)
    assert test_i.pointers == {"does": set(), "not": set()}
    assert test_i.name == "test2"
    assert test_i.keys_value_finder is key_value_finder2

def test_index_get_defaults():
    '''tests the FieldValueIndex get returns right default value when not found'''
    test_i = CC.FieldValueIndex("test", keys_value_finder=lambda x: x.i)

    assert test_i.get("a") is None

    # pretending data was added
    test_i.pointers = {"A":set([13])}
    assert test_i.get("A") == [13]
    assert test_i.get("D") is None
    
    assert test_i.get("Z", default="test") == "test"

    # default blank object returns the same object
    blank_dict = {}
    get_res = test_i.get("Z", default=blank_dict)
    assert get_res is blank_dict
    blank_dict["ere"] = 115
    assert "ere" in get_res

    assert test_i.get(None) is None

def test_index_get_copy():
    '''test that the FieldValueIndex get returns copies'''
    test_i = CC.FieldValueIndex("test", keys_value_finder=lambda x: x.i)

    # pretending data was added
    backing_set = set([13])
    test_i.pointers = {"A":backing_set}
    assert test_i.get("A") == [13]
    assert test_i.get("A") is not backing_set
    test_copy = test_i.get("A")
    backing_set.add(14)
    assert 14 not in test_copy

def test_index_clear():
    '''tests that the FieldValueIndex can clear everything'''
    test_i = CC.FieldValueIndex("test", keys_value_finder=lambda x: x.i)

    # pretending data was added
    backing_set = set([13])
    test_i.pointers = {"A":backing_set}
    assert len(test_i.pointers) > 0
    prev_pointers = test_i.pointers

    test_i.clear()
    assert test_i.pointers == {}
    # test didn't create new dict
    assert len(prev_pointers) == 0

def test_FVI_get_secondary_keys():
    '''tests that the FieldValueIndex can find right secondary keys with a privided function'''
    test_i = CC.FieldValueIndex("col_A", keys_value_finder=lambda x: [x["A"]])

    item = {"A":"a", "p_key":54, "B": [1,2,3,4]}

    assert test_i.get_item_secondary_keys(54, item) == ["a"]

def test_FVI_get_secondary_keys_copies():
    '''tests that the FieldValueIndex returns a copy and the custom function does not need to implement it'''
    test_i_2 = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])

    item = {"A":"a", "p_key":54, "B": [1,2,3,4]}

    assert test_i_2.get_item_secondary_keys(54, item) is not item["B"]

def test_FVI_get_secondary_keys_none():
    '''tests that the FieldValueIndex returns empty list if value finder returns not found using None'''
    test_i = CC.FieldValueIndex("col_A", keys_value_finder=lambda x: [x.get("Z")] if x.get("Z") else None)

    item = {"A":"a", "p_key":54, "B": [1,2,3,4]}

    assert test_i.get_item_secondary_keys(54, item) == []

def test_add_item():
    '''test that FieldValueIndex can add things to index and it gets tracked'''
    test_i = CC.FieldValueIndex("col_A", keys_value_finder=lambda x: [x["A"]])

    item = {"A":"a", "p_key":54, "B": [1,2,3,4]}
    test_i.add_item(54, item)

    assert test_i.pointers == {"a": set([54])}

    test_i.add_item(65, {"A": "Z"})
    test_i.add_item(62, {"A": "a"})

    assert test_i.pointers == {"a": set([54, 62]), "Z": set([65])}

def test_add_item_list_col():
    '''test that FieldValueIndex can add things to index and it gets tracked if told finding keys is a list of items'''
    test_i = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])

    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})

    assert test_i.pointers == {1: set([54]), 2: set([54]), 3: set([54]), 4: set([54])}

    test_i.add_item(65, {"B": [1, 5]})
    test_i.add_item(62, {"B": [6]})

    assert test_i.pointers == {1: set([54, 65]), 2: set([54]), 3: set([54]), 4: set([54]), 5: set([65]), 6: set([62])}

def test_add_item_structure_same():
    '''test that FieldValueIndex does not replace structures when adding new data'''
    test_i = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])

    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})

    assert test_i.pointers == {1: set([54]), 2: set([54]), 3: set([54]), 4: set([54])}
    tracker = test_i.pointers[1]

    test_i.add_item(65, {"B": [1, 5]})

    assert 65 in tracker

def test_remove_item():
    '''test that FieldValueIndex removes keys correctly'''
    test_i = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])
    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})
    test_i.add_item(65, {"B": [1, 5]})
    test_i.add_item(62, {"B": [6]})

    assert test_i.pointers == {1: set([54, 65]), 2: set([54]), 3: set([54]), 4: set([54]), 5: set([65]), 6: set([62])}

    test_i.remove_item(62, {"B": [6]})

    assert test_i.pointers == {1: set([54, 65]), 2: set([54]), 3: set([54]), 4: set([54]), 5: set([65])}

    test_i.remove_item(65, {"B": [1, 5]})

    assert test_i.pointers == {1: set([54]), 2: set([54]), 3: set([54]), 4: set([54])}

def test_set_item_keys():
    '''test that FieldValueIndex behavies correctly for setting keys for an item'''
    test_i = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])
    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})
    test_i.add_item(65, {"B": [1, 5]})
    test_i.add_item(62, {"B": [6]})

    test_i.set_item_keys(65, test_i.get_item_secondary_keys(65, {"B": [1, 5]}), {"B": [8, 3]})

    assert test_i.pointers == {1: set([54]), 2: set([54]), 3: set([54, 65]), 4: set([54]), 8: set([65]), 6: set([62])}

def test_set_item_keys_missing_key():
    '''test FieldValueIndex behaves as expected when old keys are wrong'''
    test_i = CC.FieldValueIndex("col_B", keys_value_finder=lambda x: x["B"])
    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})
    test_i.add_item(65, {"B": [1, 5]})
    test_i.add_item(62, {"B": [6]})

    test_i.set_item_keys(65, test_i.get_item_secondary_keys(65, {"B": [1, 3]}), {"B": [8, 3]})

    assert test_i.pointers == {1: set([54]), 2: set([54]), 3: set([54, 65]), 4: set([54]), 5: set([65]), 8: set([65]), 6: set([62])}

def test_existance_index_get_secondary():
    '''test ObjContainsFieldIndex gets the right keys'''
    test_i = CC.ObjContainsFieldIndex("col_B", keys_value_finder=lambda x: x.get("B"))

    assert test_i.get_item_secondary_keys(54, {"B":"a"}) == ["does"]
    assert test_i.get_item_secondary_keys(54, {"A":"a"}) == ["not"]

def test_existance_index_add_item():
    '''test ObjContainsFieldIndex tracks added items'''
    test_i = CC.ObjContainsFieldIndex("col_B", keys_value_finder=lambda x: x.get("B"))
    test_i.add_item(54, {"A":"a", "p_key":54, "B": [1,2,3,4]})
    test_i.add_item(65, {"B": [1, 5]})
    test_i.add_item(62, {"A": "z"})

    assert test_i.pointers == {"does":set([54, 65]), "not":set([62])}

def test_default_keys_value_finder():
    '''test leaving to default version of finding keys finds properly'''
    test_i = CC.FieldValueIndex("B")
    item = {"B": [1,2,3,4]}
    assert test_i.get_item_secondary_keys(54, item) == [1,2,3,4]
    assert test_i.get_item_secondary_keys(54, item) is not item["B"]

    dict_result = test_i.get_item_secondary_keys(54, {"B": {"key1": [1,2], "key2": "A"}})
    dict_result.sort()
    assert dict_result == ["key1", "key2"]

    assert test_i.get_item_secondary_keys(54, {"B": 1}) == [1]

def test_default_keys_value_finder_not_found():
    '''test leaving to default version of finding keys secoundary keys are empty if not found'''
    test_i = CC.FieldValueIndex("B")

    assert test_i.get_item_secondary_keys(54, {"A": "a"}) == []