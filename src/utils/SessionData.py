from datetime import datetime, timedelta
import typing
import src.DialogNodes.BaseType as BaseType
from src.utils.Enums import ITEM_STATUS

class SessionData:
    DEFAULT_TTL = 600
    def __init__(self, timeout_duration=None) -> None:
        self.linked_nodes:list[BaseType.BaseNode] = []
        timeout_duration = timeout_duration if timeout_duration is not None else timedelta(seconds=SessionData.DEFAULT_TTL)
        self.set_TTL(timeout_duration)
        # self.timeout:typing.Union[datetime, None] after above call
        self.data:"dict[str, typing.Any]" = {}
        self.status = ITEM_STATUS.INACTIVE

    def set_TTL(self, timeout_duration=None):
        '''sets the session timeout to the specified amount of time from now. a total time duration of -1 means no timeout'''
        timeout_duration = timeout_duration if timeout_duration is not None else timedelta(seconds=SessionData.DEFAULT_TTL)
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

        # time_left = min(self.time_left(),*[node.time_left() for node in self.linked_nodes])
        # for node in self.linked_nodes:
        #     node.set_TTL(time_left)

    def get_linked_nodes(self):
        '''get nodes that are linked together through this session'''
        return self.linked_nodes
    
    def add_node(self, active_node):
        '''adds the given active node into the linked nodes tracked by this session. checks to make sure node is not a repeat'''
        if id(active_node) in [id(node) for node in self.linked_nodes]:
            return False
        self.linked_nodes.append(active_node)
        return True

    def clear_session_history(self, exceptions=[]):
        '''clears the linked nodes recorded by this session except for anything passed in exceptions.DOES NOT DELETE NODES. 
        use handler to close nodes'''
        if len(exceptions) > 0:
            # there are exceptions that we don't want to delete
            deletable = []
            for node in self.linked_nodes:
                if node not in exceptions:
                    deletable.append(node)

            for node in deletable:
                self.linked_nodes.remove(node)
        else:
            self.linked_nodes.clear()

    def time_left(self) -> timedelta:
        '''returns the difference between session timeout and current time'''
        if self.timeout is None:
            return None
        return self.timeout - datetime.utcnow()
    
    def activate(self):
        self.status = ITEM_STATUS.ACTIVE

    def is_active(self):
        return self.status == ITEM_STATUS.ACTIVE
        
    def notify_closing(self):
        self.status = ITEM_STATUS.CLOSING

    def close(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.status = ITEM_STATUS.CLOSED

    def __del__(self):
        print("destrucor for session data. id'd", id(self))
