from enum import Enum
NODE_STATUS= {
    "inactie" : 0,
    "active" : 1,
    "scheduled_close" : 2,
    "closing" : 3,
    "closed" : 4
}

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