import src.DialogNodes.BaseType as BaseType

class ChildTwoGraphNode(BaseType.BaseGraphNode):
    TYPE = "ChildTwo"
    ADDED_FIELDS='''
options:
  - name: CN2
    default: B'''
    SCHEMA = '''
type: object
properties:
    c:
        type: string'''
    VERSION="1.0.0"

class ChildTwoNode(BaseType.BaseNode):
    pass
