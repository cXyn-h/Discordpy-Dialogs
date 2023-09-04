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

POSSIBLE_PURPOSES = {
    "FILTER": 1,
    "CALLBACK": 2,
    "TRANSITION_FILTER":3,
    "TRANSITION_CALLBACK":4,
    "ACTION": 2,
    "TRANSITION_ACTION": 4
}