import src.DialogEvents.BaseEvent as BaseEvent
class SimpleExceptionEvent(BaseEvent.BaseEvent):
    def __init__(self, event, exception, section):
        self.event = event
        self.exception = exception
        self.section = section