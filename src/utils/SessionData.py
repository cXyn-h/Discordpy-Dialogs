from datetime import datetime, timedelta
import typing
import src.DialogNodes.BaseType as BaseType
from src.utils.Enums import ITEM_STATUS

class SessionData:
    
    def __init__(self, timeout_duration=timedelta(minutes=10)) -> None:
        self.linked_nodes:list[BaseType.BaseNode] = []
        self.set_TTL(timeout_duration)
        # self.timeout:typing.Union[datetime, None] after above call
        self.data:"dict[str, typing.Any]" = {}
        self.status = ITEM_STATUS.INACTIVE

    def set_TTL(self, timeout_duration=timedelta(minutes=10)):
        '''sets the session timeout to the specified amount of time from now. a total time duration of -1 means no timeout'''
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
        #TODO: checking if node is already inside?
        self.linked_nodes.append(active_node)

    def clear_session_history(self, exceptions=[]):
        if len(exceptions) > 0:
            deletable = []
            for node in self.linked_nodes:
                if node not in exceptions:
                    deletable.append(node)

            for node in deletable:
                self.linked_nodes.remove(node)
        else:
            self.linked_nodes.clear()

    def time_left(self) -> timedelta:
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
