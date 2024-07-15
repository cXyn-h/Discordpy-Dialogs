import src.utils.DotNotator as DotNotator

def test_object_custom_parser_does_not_handle():
    '''testing custom parser getting passed a key where it doesn't take care of it goes to the default dot notator behavior'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            if names[0] == "test":
                return None
            elif names[0] == 2:
                return [], self.a

    item = test()
    assert DotNotator.parse_dot_notation(["b"], item) == [1,2,3]

def test_object_custom_parser_none():
    ''''testing custom parser can return none without things breaking and that goes through to the default dot notator behavior'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            if names[0] == "test":
                return None
            elif names[0] == 2:
                return [], self.a

    item = test()
    assert DotNotator.parse_dot_notation(["test"], item) == "test"

def test_object_custom_parser_finishes():
    ''''testing custom parser returning that it has finished is properly recognized'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            if names[0] == "test":
                return None
            elif names[0] == 2:
                return [], self.a

    item = test()
    assert DotNotator.parse_dot_notation([2], item) == 2

    assert DotNotator.parse_dot_notation([2, 4], item) == 2

def test_object_custom_parser_partial():
    ''''testing custom parser returning that it partially compeleted something gets finished by notator'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            if names[0] == "test":
                return None
            elif names[0] == 2:
                return [], self.a
            elif names[0] == "b":
                names.pop(0)
                return names, self.b

    item = test()
    assert DotNotator.parse_dot_notation(["b"], item) == [1,2,3]
    assert DotNotator.parse_dot_notation(["b", 0], item) == 1

def test_object_custom_parser_no_endless_loop():
    ''''testing custom parser returning what it was passed does not cause an endless loop'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            if names[0] == "error":
                return names, self

    item = test()

    assert DotNotator.parse_dot_notation(["error"], item) == None

def test_object_custom_parser_name():
    ''''testing custom parser finds the custom function when it has a different name'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def keys(self, names):
            if names[0] == "test":
                return None
            elif names[0] == 2:
                return [], self.a
            elif names[0] == "b":
                names.pop(0)
                return names, self.b

    item = test()
    assert DotNotator.parse_dot_notation(["b"], item, custom_func_name="keys") == [1,2,3]
    assert DotNotator.parse_dot_notation(["b", 0], item, custom_func_name="keys") == 1
        
def test_custom_fail():
    '''test if custom parser has an error it goes back to default handling'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            raise Exception("re")
    item = test()
    assert DotNotator.parse_dot_notation(["a"], item) == 2
    assert DotNotator.parse_dot_notation(["b"], item) == [1,2,3]
    assert DotNotator.parse_dot_notation(["error"], item) is None

def test_custom_bad_return():
    '''test if custom parser return is not a tuple it returns to default handling'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            return names
    item = test()
    assert DotNotator.parse_dot_notation(["a"], item) == 2
    assert DotNotator.parse_dot_notation(["b"], item) == [1,2,3]
    assert DotNotator.parse_dot_notation(["error"], item) is None

def test_custom_bad_signiture():
    '''test if custom parser does not accept the right paramters, it returns to default handling'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self):
            return [], self.a
    item = test()
    assert DotNotator.parse_dot_notation(["a"], item) == 2
    assert DotNotator.parse_dot_notation(["b"], item) == [1,2,3]
    assert DotNotator.parse_dot_notation(["error"], item) is None

def test_custom_add_keys():
    '''test custom parser doing whatever it wants with search, even adding keys, works'''
    class test:
        a = 2
        b = [1,2,3]
        test = "test"
        def test_m(self):
            pass
        def custom_parse_dot(self, names):
            return ["b", 0], self
    item = test()
    assert DotNotator.parse_dot_notation(["a"], item) == 1