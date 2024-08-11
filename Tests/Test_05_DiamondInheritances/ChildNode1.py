import src.DialogNodes.BaseType as BaseType

class ChildOneGraphNode(BaseType.BaseGraphNode):
    TYPE = "ChildOne"
    ADDED_FIELDS='''
options:
  - name: CN1
    default: A'''
    SCHEMA = '''
type: object
properties:
    d:
        type: string'''
    VERSION="1.0.0"

class ChildOneNode(BaseType.BaseNode):
    pass
