import Tests.Test_05_DiamondInheritances.ChildNode3 as CN3
import Tests.Test_05_DiamondInheritances.ChildNode4 as CN4

class GrandchildGraphNode(CN3.ChildThreeGraphNode, CN4.ChildFourGraphNode):
    TYPE = "Grandchild"
    ADDED_FIELDS='''
options:
  - name: GC
    default: C'''
    SCHEMA = ''''''
    VERSION="1.0.0"

class GrandchildNode(CN3.ChildThreeNode, CN4.ChildFourNode):
    pass
