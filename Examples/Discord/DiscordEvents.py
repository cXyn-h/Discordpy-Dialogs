from typing import Any
import src.DialogEvents.BaseEvent as BaseEvent
import yaml


class MenuClickEvent(BaseEvent.BaseEvent):
    '''NOT IN USE BECAUSE CAN'T FIGURE OUT INTEGRATING IT'''
    FILTERS='''- clicked_this_menu'''

    def __init__(self, interaction) -> None:
        #TODO: this is causing a lot of errors. how to duck type this to be same as iteraction so it works with when this event isn't used
        # Not sure how to use rn
        super().__init__()
        self.interaction = interaction

    def get_event_filters(self):
        return yaml.safe_load(self.__class__.FILTERS)
    
    def __getattribute__(self, __name: str) -> Any:
        #TODO: maybe this can work for Event class? Investigate
        return self.interaction.__name