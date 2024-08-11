import Tests.Test_05_DiamondInheritances.ChildNode2 as CN2

class ChildFourGraphNode(CN2.ChildTwoGraphNode):
    TYPE = "ChildFour"
    ADDED_FIELDS='''
options:
  - name: CN2
    default: B'''
    SCHEMA = '''
type: object
properties:
    a:
        type: string'''
    VERSION="1.0.0"

class ChildFourNode(CN2.ChildTwoNode):
    pass
