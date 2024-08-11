import Tests.Test_05_DiamondInheritances.ChildNode1 as CN1

class ChildThreeGraphNode(CN1.ChildOneGraphNode):
    TYPE = "ChildThree"
    ADDED_FIELDS='''
options:
  - name: CN2
    default: B'''
    SCHEMA = '''
type: object
properties:
    b:
        type: string'''
    VERSION="1.0.0"

class ChildThreeNode(CN1.ChildOneNode):
    pass
