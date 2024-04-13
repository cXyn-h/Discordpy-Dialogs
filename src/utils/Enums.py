from enum import Enum
class ITEM_STATUS(Enum):
    INACTIVE = 0    # paused, turned off, is still there and wanted
    ACTIVE = 1      # running and wanted
    CLOSING = 2     # in process of final clean up
    CLOSED = 3      # cleaned up, not wanted anymore and likely to be deleted soon

EXCEPTION_LEVEL = {
    "warnings": 0, # raise exception on warnings as well as exceptions
    "exceptions": 1, # suppress warnings, raise exceptions
    "ignore": 2, # suppress everything
}

class POSSIBLE_PURPOSES(Enum):
    TRANSITION_COUNTER="transition_counter"
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

class TASK_STATE(Enum):
    WAITING=2
    EVENT=3
    CLOSING=4