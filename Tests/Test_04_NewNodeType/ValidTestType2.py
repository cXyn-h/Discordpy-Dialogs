import typing
from src.DialogNodes.BaseType import BaseNode
import src.DialogNodes.BaseType as BaseType
import src.utils.SessionData as SessionData
from datetime import timedelta

# valid 

class ValidTestGraphNode(BaseType.BaseGraphNode):
    TYPE = "ValidTest"
    FIELDS='''
options:
  - name: testing'''
    SCHEMA = '''
type: object
properties:
    testing:
        type: string'''
    VERSION="1.0.0"
    pass

    def activate_node(self, session:typing.Union[None, SessionData.SessionData]=None) -> "BaseNode":
        return ValidTestNode(self, session, timeout_duration=timedelta(seconds=self.TTL))

class ValidTestNode(BaseType.BaseNode):
    pass
