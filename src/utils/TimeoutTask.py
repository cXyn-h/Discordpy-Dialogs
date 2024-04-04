import asyncio
from asyncio.events import AbstractEventLoop
import typing
from datetime import datetime
from src.utils.Enums import TASK_STATE, ITEM_STATUS
# for better logging
import logging
# has setup for format that is pretty good looking 
import src.utils.LoggingHelper as logHelper

task_clean_logger = logging.getLogger("Task Cleaner")
logHelper.use_default_setup(task_clean_logger)
task_clean_logger.setLevel(logging.DEBUG)

class HandlerTimeoutTask(asyncio.Task):
    def __init__(self,
                 timeoutable,
                 timeout_handler,
                 close_handler,
                 loop: AbstractEventLoop=None,
                 name: typing.Union[str, None]=None) -> None:
        if loop is None:
            loop = asyncio.get_event_loop()
        # loop.create_task(coro=self.task_runner(), name=name)
        super().__init__(coro=self.task_runner(), loop=loop, name=name)
        self.timeoutable = timeoutable
        self.timeout_handler = timeout_handler
        self.close_handler = close_handler

        self.state = TASK_STATE.WAITING
        task_clean_logger.info(f"task for item <{id(timeoutable)}> type <{type(timeoutable)}> created")

    async def task_runner(self):
        task_clean_logger.debug(f"task for item <{id(self.timeoutable)}> starting task run")
        while self.timeoutable.timeout is not None and datetime.utcnow() <= self.timeoutable.timeout:
            # big outer loop to catch if timeout has been updated at the end
            while datetime.utcnow() < self.timeoutable.timeout:
                #TODO: this can cause infinite loop, fix later
                now = datetime.utcnow()
                delay = max(0, (self.timeoutable.timeout - datetime.utcnow()).total_seconds())
                task_clean_logger.debug(f"task for item <{id(self.timeoutable)}> sleeping for <{delay}> now <{now}> timeout <{self.timeoutable.timeout}> check <{now < self.timeoutable.timeout}>")
                await asyncio.sleep(delay)
                if self.timeoutable.status == ITEM_STATUS.CLOSED or self.timeoutable.timeout is None:
                    task_clean_logger.info(f"task for item <{id(self.timeoutable)}> awoke to timout not being needed. returning")
                    return
            self.state = TASK_STATE.EVENT
            task_clean_logger.info(f"task for item <{id(self.timeoutable)}> doing timeout event callbacks")
            await self.timeout_handler(self.timeoutable)
            if self.timeoutable.timeout is not None and self.timeoutable.timeout <= datetime.utcnow():
                task_clean_logger.info(f"task for item <{id(self.timeoutable)}> found needs to close item")
                self.state = TASK_STATE.CLOSING
                await self.close_handler(self.timeoutable)
        task_clean_logger.info(f"task for item <{id(self.timeoutable)}> on way to exiting task")
