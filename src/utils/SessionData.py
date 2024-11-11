from datetime import datetime, timedelta
import typing
import uuid

import src.DialogNodes.BaseType

from src.utils.Enums import ITEM_STATUS
import src.utils.DotNotator as DotNotator

class SessionData:
    DEFAULT_TTL = 600
    def __init__(self, timeout_duration=None) -> None:
        self.id = uuid.uuid4().hex
        self.linked_nodes:list[src.DialogNodes.BaseType.BaseNode] = []
        timeout_duration = timeout_duration if timeout_duration is not None else timedelta(seconds=SessionData.DEFAULT_TTL)
        self.set_TTL(timeout_duration)
        # self.timeout:typing.Union[datetime, None] after above call
        self.data:"dict[str, typing.Any]" = {}
        self.status = ITEM_STATUS.INACTIVE

    def set_TTL(self, timeout_duration:"typing.Optional[typing.Union[timedelta, datetime]]"):
        if isinstance(timeout_duration, datetime):
            self.timeout = timeout_duration
            return True
        elif isinstance(timeout_duration, timedelta): 
            if timeout_duration.total_seconds() == -1:
                # specifically, don't time out
                self.timeout = None
            else:
                self.timeout = datetime.utcnow() + timeout_duration
            return True
        elif timeout_duration is None:
            self.timeout = None
            return True
        return False

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

    def serialize(self):
        serialized = {}
        serialized.update({"linked_nodes": [node.id for node in self.linked_nodes], "status": self.status.name, "timeout": self.timeout, "data": self.data})
        return serialized

    def can_set(self, location):
        '''checks wether field specified in location is something node definition allows overwritting or adding. only addresses data fields for node'''
        if isinstance(location, str):
            split_names = location.split(".")
        elif isinstance(location, list):
            split_names = location

        return split_names[0] not in ["id", "status", "linked_nodes"]
    
    def can_delete(self, location):
        if isinstance(location, str):
            split_names = location.split(".")
        elif isinstance(location, list):
            split_names = location

        # don't allow deleting any attributes declared on the node. only things in data
        if split_names[0] in self.data:
            return True
        return False
    
    def set_data(self, location, data):
        '''function that callbacks should use to set data on active node'''
        # setting up split list of names for finding
        if isinstance(location, str):
            split_names = location.split(".")
        elif isinstance(location, list):
            split_names = location

        # always have at least one place to look for in location
        if len(split_names) < 1 or not self.can_set(split_names):
            return False

        # data fields can have names that overlap with functions on the object, in that case they have to go into data
        # any attributes cannot reappear in data. either declared attribute or data
        # certain attributes cannt be replaced, maybe can't edit further inside either
        # data is free space for function use
        attr_names = [attr_name for attr_name in dir(self) if not attr_name.startswith('__') and not callable(getattr(self, attr_name))]

        #TODO: type checking and more constraints
        if split_names[0] in attr_names:
            if len(split_names) == 1 and split_names[0] == "timeout":
                return self.set_TTL(data)
            # is defined as attribute by class, not allowing to be able to add data attributes
            setattr(self, split_names[0], data)
            return True
        else:
            if len(split_names) > 1:
                location = DotNotator.parse_dot_notation(split_names[:-1], self, None, custom_func_name="get_data")
                if location == None:
                    return False
                if isinstance(location, dict):
                    location[split_names[-1]] = data
                elif isinstance(location, list):
                    location.append(data)
                elif issubclass(location.__class__, src.DialogNodes.BaseType.BaseNode) or isinstance(location, SessionData):
                    location.set_data(split_names[-1], data)
                else:
                    setattr(self, split_names[0], data)
            else:
                self.data[split_names[0]] = data
            return True

    def delete_data(self, location):
        if isinstance(location, str):
            split_names = location.split(".")
        elif isinstance(location, list):
            split_names = location

        if len(split_names) < 1 or not self.can_delete(split_names):
            return None

        if split_names[0] in self.data:
            field_name = split_names[-1]
            if len(split_names) > 1:
                location = DotNotator.parse_dot_notation(split_names[:-1], self, None, custom_func_name="get_data")
                if location == None:
                    return None
                if isinstance(location, dict):
                    if field_name in location:
                        removed = location[field_name]
                        del location[field_name]
                        return removed
                elif isinstance(location, list):
                    if not isinstance(field_name, int):
                        return None
                    return location.pop(field_name)
                elif issubclass(location.__class__, src.DialogNodes.BaseType.BaseNode) or isinstance(location, SessionData):
                    location.delete_data(split_names[-1])
                else:
                    if hasattr(location, field_name):
                        removed = getattr(location, field_name)
                        delattr(location, field_name)
                        return removed
            else:
                # split names only has one item is the field name. it also has to be in self.data
                removed = self.data[field_name]
                del self.data[field_name]
                return removed
    
    def get_data(self, search):
        '''custom dot parsing function for this class to find data storage variable/location'''
        attr_names = [attr_name for attr_name in dir(self) if not attr_name.startswith('__') and not callable(getattr(self, attr_name))]
        # get all names of data attributes. no methods.
        if search[0] in attr_names:
            return search[1:], getattr(self, search[0])
        elif search[0] in self.data:
            return search [1:], self.data[search[0]]
        else:
            # if fuction name or other thing that is not a data variable, return case that would cause stop looking
            return [], None

    def close(self):
        '''callback for when node is about to close that I don't want showing up in list of custom callbacks. if overriding
        child class, be sure to call parent'''
        self.status = ITEM_STATUS.CLOSED

    def __del__(self):
        print("destrucor for session data. id'd", id(self))
