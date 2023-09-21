import src.DialogNodes.BaseType as BaseType

# INVALID because inital look at schema shows invalid

class TestGraphNode(BaseType.BaseGraphNode):
    TYPE = "Test"
    DEFINITION='''
options:[]'''
    SCHEMA = '''
sdfsdf'''
    # VERSION="1.0.0"
    pass

class TestNode(BaseType.BaseNode):
    pass
