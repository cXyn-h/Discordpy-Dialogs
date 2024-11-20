import asyncio
from asyncio.events import AbstractEventLoop
import typing
from datetime import datetime
from src.utils.Enums import TASK_STATE, ITEM_STATUS
# for better logging
import logging
# has setup for format that is pretty good looking 
import src.utils.LoggingHelper as logHelper
from functools import reduce

task_logger = logging.getLogger("tasks")
logHelper.use_default_setup(task_logger)
task_logger.setLevel(logging.DEBUG)

class HandlerTask(asyncio.Task):
    '''base task object for any handler tasks. takes in a callback function that does the meat of the task. Expected to be a function of the handler.
    Basic backbone of the task is to use locking tasks for wait tasks to wait for before starting this task.
    Any extra variables and how to pass them to handler function or other modifications to calling that function happen in do_task'''
    def __init__(self, handler_func, loop:AbstractEventLoop=None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(coro=self.task_runner(), loop=loop, name=name)

        self.type = "Base"
        if locking_tasks is None:
            locking_tasks = []
        self.locking_tasks = locking_tasks
        self.waiting_period_sec = waiting_period_sec
        self.handler_func = handler_func
        self.scheduled_time = datetime.utcnow()
        self.start_time = None
        self.stop_time = None

    async def task_runner(self):
        while not reduce(lambda x, y: x and y, [task.done() for task in self.locking_tasks], True):
            task_logger.debug(f"task <{id(asyncio.current_task())}><{self.type}> sleeping for another <{self.waiting_period_sec}> seconds")
            await asyncio.sleep(self.waiting_period_sec)
        task_logger.debug(f"task <{id(asyncio.current_task())}><{self.type}> starting handling")
        self.start_time = datetime.utcnow()
        result = await self.do_task()
        task_logger.debug(f"task <{id(asyncio.current_task())}><{self.type}> finished handling")
        self.stop_time = datetime.utcnow()
        return result

    async def do_task(self):
        return await self.handler_func()

class HandleEventTask(HandlerTask):
    def __init__(self, handler_func, event_type, event, loop: AbstractEventLoop = None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, loop=loop, name=name, locking_tasks=locking_tasks, waiting_period_sec=waiting_period_sec)
        self.event_type = event_type
        self.event = event
        self.type = "EventTask"

    async def do_task(self):
        return await self.handler_func(self.event_type, self.event, self.waiting_period_sec)
    
class HandlerSystemEventTask(HandleEventTask):
    def __init__(self, handler_func, event_type, event, loop: AbstractEventLoop = None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, event_type, event, loop, name, locking_tasks, waiting_period_sec)
        self.type = "SystemTask"

    async def do_task(self):
        return await self.handler_func()

class HandleSessionEventTask(HandlerTask):
    def __init__(self, handler_func, session, event_type, event, loop:AbstractEventLoop=None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, loop=loop, name=name, locking_tasks=locking_tasks, waiting_period_sec=waiting_period_sec)
        self.session = session
        self.event_type = event_type
        self.event = event
        self.type = "SessionEventTask"

    async def do_task(self):
        return await self.handler_func(self.session, self.event_type, self.event, self.node_tasks)
    
    def set_node_tasks(self, node_tasks):
        self.node_tasks = node_tasks
    
class HandleNodeEventTask(HandlerTask):
    def __init__(self, handler_func, active_node, event_type, event, loop:AbstractEventLoop=None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, loop=loop, name=name, locking_tasks=locking_tasks, waiting_period_sec=waiting_period_sec)
        self.active_node = active_node
        self.event_type = event_type
        self.event = event
        self.type = "NodeEventTask"

    async def do_task(self):
        return await self.handler_func(self.active_node, self.event_type, self.event)
    
class HandleTimeoutWaiter(HandlerTask):
    def __init__(self, handler_func, timeoutable, loop: AbstractEventLoop = None, name=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, loop=loop, name=name, locking_tasks=[], waiting_period_sec=waiting_period_sec)
        self.timeoutable = timeoutable
        self.type="TimeoutWaiter"

    async def do_task(self):
        return await self.handler_func(self.timeoutable, self.waiting_period_sec)
    
    
class HandleTimeoutTask(HandlerTask):
    def __init__(self, handler_func, timeoutable, type:typing.Literal["Node","Session"], loop:AbstractEventLoop=None, name=None, locking_tasks=None, waiting_period_sec=3) -> None:
        super().__init__(handler_func, loop=loop, name=name, locking_tasks=locking_tasks, waiting_period_sec=waiting_period_sec)
        self.timeoutable = timeoutable
        self.type = type+"TimeoutTask"

    async def do_task(self):
        return await self.handler_func(self.timeoutable, self.waiting_period_sec)