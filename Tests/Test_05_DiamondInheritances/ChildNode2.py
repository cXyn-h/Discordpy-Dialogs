import src.DialogNodes.BaseType as BaseType

class ChildTwoGraphNode(BaseType.BaseGraphNode):
    TYPE = "ChildTwo"
    ADDED_FIELDS='''
options:
  - name: CN2
    default: B'''
    SCHEMA = ''''''
    VERSION="1.0.0"

class ChildTwoNode(BaseType.BaseNode):
    pass
