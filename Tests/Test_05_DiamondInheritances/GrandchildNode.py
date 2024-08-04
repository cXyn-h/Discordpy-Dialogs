import Tests.Test_05_DiamondInheritances.ChildNode1 as CN1
import Tests.Test_05_DiamondInheritances.ChildNode2 as CN2

class GrandchildGraphNode(CN1.ChildOneGraphNode, CN2.ChildTwoGraphNode):
    TYPE = "Grandchild"
    ADDED_FIELDS='''
options:
  - name: GC
    default: C'''
    SCHEMA = ''''''
    VERSION="1.0.0"

class GrandchildNode(CN1.ChildOneGraphNode, CN2.ChildTwoGraphNode):
    pass
