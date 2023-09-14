from datetime import datetime, timedelta
import typing
import src.DialogNodes.BaseType as BaseType

class SessionData:
    
    def __init__(self, timeout_duration=timedelta(minutes=10)) -> None:
        self.linked_nodes:list[BaseType.BaseNode] = []
        self.set_TTL(timeout_duration)
        # self.timeout:typing.Union[datetime, None] after above call
        self.data:"dict[str, typing.Any]" = {}

    def set_TTL(self, timeout_duration=timedelta(minutes=10)):
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

        # time_left = min(self.time_left(),*[node.time_left() for node in self.linked_nodes])
        # for node in self.linked_nodes:
        #     node.set_TTL(time_left)

    def get_linked_nodes(self):
        return self.linked_nodes
    
    def add_node(self, active_node):
        #TODO: checking if node is already inside?
        self.set_TTL()
        self.linked_nodes.append(active_node)

    def clear_session_history(self):
        self.linked_nodes = []

    def time_left(self) -> timedelta:
        return self.timeout - datetime.utcnow()

