import pytest
import yaml
import src.DialogHandler as DialogHandler
import src.DialogNodeParsing as DialogParser
import src.DialogNodes.BaseType as BaseType
import src.utils.CallbackUtils as NodetionCbUtils
import src.utils.HandlerTasks as HandlerTasks
from src.utils.Enums import POSSIBLE_PURPOSES, ITEM_STATUS
import asyncio

GRAPH = '''
nodes:
  - id: node1
    graph_start:
      ping:
    events:
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
      ping:
        actions:
        - wait:
            time: 2
            cycles: 3
  - id: node2
    graph_start:
      ping:
    events:
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
      ping:
        actions:
        - wait:
            time: 3
            cycles: 3
'''

@NodetionCbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], has_parameter="always", schema={"type": "number"})
async def wait(datapack:NodetionCbUtils.CallbackDatapack):
    time = int(datapack.base_parameter["time"])
    for i in range(datapack.base_parameter["cycles"]):
        await asyncio.sleep(time)

def setup_handler(settings=None, graph_string=None):
    
    if settings is None:
        settings = DialogHandler.HandlerSettings()
    if graph_string is None:
        graph_string = GRAPH
    loadded_yaml = yaml.safe_load(graph_string)
    nodes = {}
    for node in loadded_yaml["nodes"]:
        parsed_node = DialogParser.parse_node(node)
        nodes[parsed_node.id] = parsed_node
    handler = DialogHandler.DialogHandler(graph_nodes=nodes, settings=settings)
    handler.register_function(wait, {})
    return handler

@pytest.mark.asyncio
async def test_handle_event_finishes():
    '''test to make sure handle_event can handle running event on a node'''
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    session_graph = '''
nodes:
  - id: node1
    TTL: -1
    graph_start:
      ping:
    events:
      ping:
        actions:
        - wait:
            time: 2
            cycles: 1
'''
    settings = DialogHandler.HandlerSettings()
    handler = setup_handler(settings, session_graph)
    
    await handler.start_at("node1","ping", {"name":"ping1"})

    task = handler.notify_event("ping", {"name":"ping1"})
    assert len(task.locking_tasks) == 0
    await asyncio.sleep(0.5)
    node_event_tasks = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])
    for task in node_event_tasks:
        if task.event_type == "ping":
            first_node_event_task = task
    assert first_node_event_task is not None
    assert first_node_event_task.start_time is not None
    await asyncio.sleep(2)
    assert first_node_event_task.done()
    assert task.done()

@pytest.mark.asyncio
async def test_handle_event_strict_order():
    '''test to make sure handle_event strict order makes sure second event doesn't start until after first finishes'''
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    session_graph = '''
nodes:
  - id: node1
    TTL: -1
    graph_start:
      ping:
    events:
      ping:
        actions:
        - wait:
            time: 2
            cycles: 1
'''
    settings = DialogHandler.HandlerSettings(strict_event_order=True)
    handler = setup_handler(settings, graph_string=session_graph)
    
    await handler.start_at("node1","ping", {"name":"ping1"})

    task = handler.notify_event("ping", {"name":"ping1"})
    task2 = handler.notify_event("ping", {"name":"ping2"})

    await asyncio.sleep(0.5)
    node_event_tasks = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])
    assert len(node_event_tasks) == 1
    node_event_task1 = node_event_tasks[0]
    assert node_event_task1.start_time is not None
    assert task2.start_time is None
    await asyncio.sleep(2)
    assert node_event_task1.done()
    await asyncio.sleep(4)
    assert task2.start_time is not None
    assert not task2.done()
    node_event_tasks = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])
    assert len(node_event_tasks) == 2
    for node_event_task in node_event_tasks:
        if node_event_task.event["name"] == "ping2":
            node_event_task2 = node_event_task
    assert node_event_task2.start_time is not None
    await asyncio.sleep(2)

@pytest.mark.asyncio
async def test_timeouts_created():
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    handler = setup_handler()
    # not recommended to change TTL, but this is testing
    handler.graph_node_indexer.get_ref("node1").TTL = 1
    handler.graph_node_indexer.get_ref("node2").TTL = 2

    await handler.start_at("node2", "ping", {})
    await handler.start_at("node1", "ping", {})
    # timeouts in 1 and 2 seconds
    assert len(handler.active_node_cache) == 2
    for active_node in handler.active_node_cache.cache.values():
        if active_node.graph_node.id == "node1":
            active_node1 = active_node
    assert len(handler.advanced_event_queue) == 2 # no sessions, only two nodes timing out, no events yet
    timeout_waiter_tasks = handler.advanced_event_queue.get("TimeoutWaiter", index_name="task_type", default=[])
    assert len(timeout_waiter_tasks) == 2
    for timeout_task in timeout_waiter_tasks:
        if timeout_task.timeoutable.graph_node.id == "node1":
            node1_waiter = timeout_task
        else:
            node2_waiter = timeout_task
    await asyncio.sleep(1.5)
    # handling for node1 timeout should be 0.5 seconds in, 0.5 to done
    assert len(handler.advanced_event_queue) == 4
    assert not node1_waiter.done()
    assert not node2_waiter.done()
    assert len(handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])) == 1
    node_1_timeout_handler = handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])[0]
    assert node_1_timeout_handler.timeoutable.graph_node.id == "node1"
    assert node_1_timeout_handler.start_time is not None
    assert len(handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])) == 1
    node_1_timeout_event = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])[0]
    assert node_1_timeout_event.active_node.graph_node.id == "node1"
    assert node_1_timeout_event.start_time is not None
    await asyncio.sleep(1)
    # handling for first timeout finished, second node timeout has 0.5 seconds left
    assert node_1_timeout_event.done()
    assert node_1_timeout_handler.done()
    assert active_node1.status == ITEM_STATUS.CLOSED
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task in handler, <{id(task)}> type <{task.type}>, done? <{task.done()}> exception: <{task.exception() if task.done() else 'N/A'}>")
    assert len(handler.advanced_event_queue) == 6
    assert len(handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])) == 2
    assert "node2" in [task.timeoutable.graph_node.id for task in handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])]
    assert len(handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])) == 2
    assert "node2" in [task.active_node.graph_node.id for task in handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])]
    await asyncio.sleep(1)
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        assert task.done()
        assert task.exception() is None

@pytest.mark.asyncio
async def test_timeouts_wait():
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    handler = setup_handler(DialogHandler.HandlerSettings(strict_event_order=True))
    # not recommended to change TTL, but this is testing
    handler.graph_node_indexer.get_ref("node1").TTL = 2

    await handler.start_at("node1", "ping", {})
    event_task = handler.notify_event("ping", {"name": "ping1"})
    assert not event_task.done()
    timeout_waiter_tasks = handler.advanced_event_queue.get("TimeoutWaiter", index_name="task_type", default=[])
    assert len(timeout_waiter_tasks) == 1
    node1_waiter = timeout_waiter_tasks[0]
    # timeout in 2 seconds, event done handling in 6
    
    await asyncio.sleep(0.5)
    # timeout in 1.5 seconds, event done handling in 5.5
    assert event_task.start_time is not None

    await asyncio.sleep(2)
    # timeout has occured, event done in 3.5
    assert len(handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])) == 1
    timeout_handler:HandlerTasks.HandleTimeoutTask = handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])[0]
    assert timeout_handler.timeoutable.graph_node.id == "node1"
    assert len(timeout_handler.locking_tasks) > 0
    assert timeout_handler.start_time is None

    await asyncio.sleep(10)
    # big gap because of events having long nap times independently
    # timeout now free to handle, event is done
    assert event_task.done()
    assert timeout_handler.start_time is not None
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        assert task.done()
        assert task.exception() is None

@pytest.mark.asyncio
async def test_timeouts_block():
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    handler = setup_handler(DialogHandler.HandlerSettings(strict_event_order=True))
    # not recommended to change TTL, but this is testing
    handler.graph_node_indexer.get_ref("node1").TTL = 2

    await handler.start_at("node1", "ping", {})
    timeout_waiter_tasks = handler.advanced_event_queue.get("TimeoutWaiter", index_name="task_type", default=[])
    assert len(timeout_waiter_tasks) == 1
    node1_waiter = timeout_waiter_tasks[0]
    # timeout in 2 seconds
    await asyncio.sleep(2.5)
    # timout in middle of handling, 0.5 seconds more
    assert len(handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])) == 1
    timeout_handler:HandlerTasks.HandleTimeoutTask = handler.advanced_event_queue.get("NodeTimeoutTask", index_name="task_type", default=[])[0]
    assert timeout_handler.timeoutable.graph_node.id == "node1"
    assert timeout_handler.start_time is not None
    assert not timeout_handler.done()

    event_task = handler.notify_event("ping", {"name": "ping1"})
    await asyncio.sleep(0.1)
    assert len(handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])) == 2
    node_event_tasks = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])
    event_types = [task.event_type for task in node_event_tasks]
    assert "timeout" in event_types
    assert "ping" in event_types
    for task in node_event_tasks:
        if task.event_type == "ping":
            node_event_task = task
    assert len(node_event_task.locking_tasks) > 0
    assert node_event_task.start_time is None
    
    await asyncio.sleep(0.9)
    # timeout is done, event handling allowed to go
    assert timeout_handler.done()

    await asyncio.sleep(5)
    # # big gap because of events having long nap times independently
    # # event is now free to handle, timeout is done. though timeout closed node so event doesn't really have anything to do
    assert node_event_task.start_time is not None
    assert node_event_task.done()
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        assert task.done()
        assert task.exception() is None

@pytest.mark.asyncio
async def test_session_task_timeout():
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    session_graph = '''
nodes:
  - id: node1
    TTL: -1
    graph_start:
      ping:
        session_chaining:
          start: 2
    events:
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
  - id: node2
    graph_start:
      ping:
    events:
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
'''
    settings = DialogHandler.HandlerSettings(strict_event_order=True)
    loadded_yaml = yaml.safe_load(session_graph)
    nodes = {}
    for node in loadded_yaml["nodes"]:
        parsed_node = DialogParser.parse_node(node)
        nodes[parsed_node.id] = parsed_node
    handler = DialogHandler.DialogHandler(graph_nodes=nodes, settings=settings)
    handler.register_function(wait, {})
    
    await handler.start_at("node1","ping", {})
    # node doesn't have timeout, session has timeout in 2
    timeout_waiter_tasks = handler.advanced_event_queue.get("TimeoutWaiter", index_name="task_type", default=[])
    assert len(timeout_waiter_tasks) == 1
    for task in timeout_waiter_tasks:
        if not issubclass(task.timeoutable.__class__, BaseType.BaseNode):
            session_timeout_waiter = task
    assert session_timeout_waiter is not None
    await asyncio.sleep(2.5)
    # session should be 0.5 seconds into handling timeout
    timeout_handler_tasks = handler.advanced_event_queue.get("SessionTimeoutTask", index_name="task_type", default=[])
    assert len(timeout_handler_tasks) == 1
    for task in timeout_handler_tasks:
        if not issubclass(task.timeoutable.__class__, BaseType.BaseNode):
            session_timeout_handler = task
    assert session_timeout_handler.start_time is not None
    assert not session_timeout_waiter.done()
    await asyncio.sleep(1)
    assert session_timeout_handler.done()
    assert session_timeout_waiter.done()
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        assert task.done()
        assert task.exception() is None

@pytest.mark.asyncio
async def test_session_task_waits():
    '''test sessions cause waiting for future event node and session events from happening'''
    import logging
    import src.utils.LoggingHelper as logHelper
    test_logger = logging.getLogger('test')
    logHelper.use_default_setup(test_logger)
    test_logger.setLevel(logging.DEBUG)
    session_graph = '''
nodes:
  - id: node1
    TTL: -1
    graph_start:
      ping:
        session_chaining:
          start: 13
    events:
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
      ping:
        transitions:
        - node_names: node2
          session_chaining: chain
      testEvent2:
        actions:
        - wait:
            time: 2
            cycles: 1
  - id: node2
    TTL: -1
    events:
      testEvent1:
        actions:
        - wait:
            time: 2
            cycles: 1
      timeout:
        actions:
        - wait:
            time: 1
            cycles: 1
'''
    settings = DialogHandler.HandlerSettings()
    loadded_yaml = yaml.safe_load(session_graph)
    nodes = {}
    for node in loadded_yaml["nodes"]:
        parsed_node = DialogParser.parse_node(node)
        nodes[parsed_node.id] = parsed_node
    handler = DialogHandler.DialogHandler(graph_nodes=nodes, settings=settings)
    handler.register_function(wait, {})
    
    await handler.start_at("node1","ping", {"name":"ping1"})
    # session times out in 5 seconds
    task = handler.notify_event("ping", {"name": "ping2"})
    await task
    # unknown exactly when timeout happens, likely around five seconds
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        if task.type != "TimeoutWaiter":
            assert task.done()
            assert task.exception() is None
    first_event_task = handler.notify_event("testEvent1", {})
    second_event_task = handler.notify_event("testEvent2", {})
    # node2 handles event1 and finishes after 2 seconds
    # node1 handles event2 and finishes in 2 second but needs to wait on event1 in node2 because of session
    await asyncio.sleep(1.5)
    # because strict ordering off, events will start whatever handling doesn't conflict with each other
    # session timeout in around 4 seconds
    # node2 finishes handling in 0.5 second
    assert first_event_task.start_time is not None
    assert second_event_task.start_time is not None
    handler_session_event_tasks = handler.advanced_event_queue.get("SessionEventTask", index_name="task_type", default=[])
    for task in handler_session_event_tasks:
        if task.event_type == "testEvent1":
            first_session_event_task = task
        elif task.event_type == "testEvent2":
            second_session_event_task = task
    handler_node_event_tasks = handler.advanced_event_queue.get("NodeEventTask", index_name="task_type", default=[])
    for task in handler_node_event_tasks:
        if task.event_type == "testEvent1":
            first_node_event_task = task
        elif task.event_type == "testEvent2":
            second_node_event_task = task
    assert first_session_event_task is not None
    assert second_session_event_task is not None
    assert first_node_event_task is not None
    assert second_node_event_task is not None
    assert len(second_session_event_task.locking_tasks) > 0
    assert len(second_node_event_task.locking_tasks) > 0
    assert first_session_event_task in second_session_event_task.locking_tasks
    assert first_session_event_task in second_node_event_task.locking_tasks
    assert first_session_event_task.start_time is not None
    assert second_node_event_task.start_time is None
    assert second_session_event_task.start_time is None
    await asyncio.sleep(6)
    # node2 finishes handling first event
    # node1 allowed to start
    assert first_session_event_task.done()
    assert second_session_event_task.start_time is not None
    await asyncio.sleep(7)
    for task in handler.advanced_event_queue.cache.values():
        test_logger.debug(f"task <{id(task)}><{task.type}> done? <{task.done()}> exception? <{task.exception() if task.done() else 'N/A'}>")
        assert task.done()
        assert task.exception() is None