from enum import Enum
class ITEM_STATUS(Enum):
    INACTIVE = 0
    ACTIVE = 1
    CLOSING = 2
    CLOSED = 3

EXCEPTION_LEVEL = {
    "warnings": 0, # raise exception on warnings as well as exceptions
    "exceptions": 1, # suppress warnings, raise exceptions
    "ignore": 2, # suppress everything
}

class POSSIBLE_PURPOSES(Enum):
    FILTER= "filter"
    TRANSITION_FILTER="transition_filter"
    ACTION= "action"
    TRANSITION_ACTION= "transition_action"

class CLEANING_STATE(Enum):
    STARTING=1
    RUNNING=2
    PAUSED=3
    STOPPING=4
    STOPPED=5