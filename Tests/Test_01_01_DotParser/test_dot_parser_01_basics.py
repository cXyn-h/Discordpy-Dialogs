import src.utils.DotNotator as DotNotator

# tests for the parser that takes dot notation and finds the value

def test_simple_one_layer_dict():
    '''dictionary with strings as data and only trying to find key within dictionary no recursing'''
    item = {"A":"a", "B":"b", "C":"c", "D":"d"}
    assert DotNotator.parse_dot_notation(["A"], item) == "a"
    assert DotNotator.parse_dot_notation(["B"], item) == "b"

def test_simple_one_layer_dict_not_found():
    '''dictionary with strings as data and only trying to find key within dictionary no recursing but key not there'''
    item = {"A":"a", "B":"b", "C":"c", "D":"d"}
    assert DotNotator.parse_dot_notation(["Z"], item) == None
    assert DotNotator.parse_dot_notation(["b"], item) == None

def test_simple_one_layer_list():
    '''testing out finding things in a simple list no layering'''
    item = ["A","B","C","D"]
    assert DotNotator.parse_dot_notation([1], item) == "B"
    assert DotNotator.parse_dot_notation([3], item) == "D"

def test_simple_one_layer_list_not_found():
    '''testing out finding things in a list with indices that don't work'''
    item = ["A","B","C","D"]
    assert DotNotator.parse_dot_notation(["dfd"], item) == None
    assert DotNotator.parse_dot_notation([5], item) == None

def test_simple_object():
    '''testing finding fields of a instantiated object'''
    class test:
        a = 2
        b = 5
    item = test()

    assert DotNotator.parse_dot_notation(["a"], item) == 2
    assert DotNotator.parse_dot_notation(["b"], item) == 5

def test_simple_object_not_found():
    '''testing finding fields of an object that doesn't exist'''
    class test:
        a = 2
        b = 5
    item = test()

    assert DotNotator.parse_dot_notation(["A"], item) == None
    assert DotNotator.parse_dot_notation(["z"], item) == None

def test_simple_object_extend():
    '''testing if can find python structural or object properties. This may not be desireable'''
    class test:
        a = 2
        b = 5
        def test_m(self):
            pass
    item = test()

    assert DotNotator.parse_dot_notation(["__class__", "__name__"], item) == "test"
    assert DotNotator.parse_dot_notation(["test_m"], item) is not None

def test_two_layer_found():
    '''testing if system can find nested objects'''
    item = {"A":"a", "B":[1,2,3,4], "C":{"a":1, "b":2, "c":3}, "D":"d"}
    assert DotNotator.parse_dot_notation(["B", 0], item) == 1
    assert DotNotator.parse_dot_notation(["C", "b"], item) == 2
    assert DotNotator.parse_dot_notation(["B"], item) == [1,2,3,4]

def test_two_layer_not_found():
    '''testing if doesn't break and returns none if runs out of nesting to search or key not found'''
    item = {"A":"a", "B":[1,2,3,4], "C":{"a":1, "b":2, "c":3}, "D":"d"}
    assert DotNotator.parse_dot_notation(["a", 0], item) == None
    assert DotNotator.parse_dot_notation(["b", 5], item) == None

def test_two_layer_too_many_names():
    '''testing searching for too many nesting levels causes it to return not found'''
    item = {"A":"a", "B":[1,2,3,4], "C":{"a":1, "b":2, "c":3}, "D":"d"}
    assert DotNotator.parse_dot_notation(["a", 0, 3], item) == None
    assert DotNotator.parse_dot_notation(["D", "d"], item) == None

