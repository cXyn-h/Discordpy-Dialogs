import src.DialogHandler as DialogHandler
import src.DialogNodeParsing as DialogParser
import src.utils.callbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES, CLEANING_STATE
from datetime import datetime, timedelta
import yaml
import asyncio
import math
import pytest

import logging
import src.utils.LoggingHelper as logHelper

pytest_plugins = ('pytest_asyncio',)

clean_test_logger = logging.getLogger("test-clean")
logHelper.use_default_setup(clean_test_logger)
clean_test_logger.setLevel(logging.DEBUG)

@cbUtils.callback_settings(allowed=[POSSIBLE_PURPOSES.ACTION], has_parameter="always")
async def sleep(active_node, event, duration):
    clean_test_logger.debug(f"sleep close callback called, node is {id(active_node)} {active_node.graph_node.id} sleepign for {duration}")
    await asyncio.sleep(duration)
    clean_test_logger.debug(f"sleep close callback for node {id(active_node)} {active_node.graph_node.id} done")

@pytest.mark.asyncio
async def test_clean_info_finds_existing_next():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list1.yml"])

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})
    now = datetime.utcnow()
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    timed_out_nodes, timed_out_sessions, next_time = h.get_timed_out_info()
    assert next_time is not None
    assert abs((next_time - now).total_seconds() - 50) < 0.5
    assert len(timed_out_nodes) == 1
    assert timed_out_nodes[0].graph_node.id == "One"

@pytest.mark.asyncio
async def test_clean_info_no_actives_finds_next_is_none():
    h = DialogHandler.DialogHandler()
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    timed_out_nodes, timed_out_sessions, next_time = h.get_timed_out_info()
    assert next_time is None
    assert len(timed_out_nodes) == 0
    assert len(timed_out_sessions) == 0

@pytest.mark.asyncio
async def test_clean_info_single_timed_out_finds_next_is_none():
    h = DialogHandler.DialogHandler()
    nodes='''
id: One
TTL: 0
graph_start:
  test:
'''
    parsed_node = DialogParser.parse_node(yaml.safe_load(nodes)) 
    h.add_nodes({parsed_node.id:parsed_node})

    await h.start_at("One", "test", {})
    now = datetime.utcnow()
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    timed_out_nodes, timed_out_sessions, next_time = h.get_timed_out_info()
    assert next_time is None
    assert len(timed_out_nodes) == 1
    assert timed_out_nodes[0].graph_node.id == "One"

@pytest.mark.asyncio
async def test_start_cleaning_process():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})

    start_time = datetime.utcnow()

    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    assert (h.cleaning_status["next"] - start_time).total_seconds() < 1

@pytest.mark.asyncio
async def test_one_clean_is_right():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    start_time = datetime.utcnow()
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    assert abs((h.cleaning_status["next"] - start_time).total_seconds()) < 0.5
    assert len(h.active_nodes) == 2
    await asyncio.sleep(1)
    assert abs((h.cleaning_status["now"] - start_time).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - start_time - timedelta(seconds=5)).total_seconds()) < 0.5
    res = h.stop_cleaning()
    assert res == True
    assert len(h.active_nodes) == 1
    assert "Two" in [x.graph_node.id for x in h.active_nodes.values()]
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPING
    # at this point clean task finished this round and is sleeping for next round (longer sleep) and won't go to stopped until it wakes up again
    await asyncio.sleep(4)
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED


@pytest.mark.asyncio
async def test_repeat_clean_starts_nodes():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    start_time = datetime.utcnow()

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})
    await h.start_at("Three", "test", {})
    await h.start_at("Four", "test", {})

    creation_duration = datetime.utcnow()-start_time
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING

@pytest.mark.asyncio
async def test_repeat_clean_starts_empty():
    h = DialogHandler.DialogHandler()

    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING


@pytest.mark.asyncio
async def test_clean_should_never_run():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    # lots of tests here using node One as the one that times out first clean.
    await h.start_at("One", "test", {})

    start_time = datetime.utcnow()
    h.cleaning_task = asyncio.get_event_loop().create_task(h.clean_task(delay=0))
    counter = 0
    while not h.cleaning_task.done() and counter < 20:
        assert h.cleaning_status["state"] != CLEANING_STATE.RUNNING
        await asyncio.sleep(1)
        counter += 1
    if counter == 20:
        assert "might be long running clean, or other weirdness" == "fix that"
    assert len(h.active_nodes) == 1

@pytest.mark.asyncio
async def test_cleaning_unpauses():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    start_time = datetime.utcnow()

    started = h.start_cleaning()
    assert started == True
    paused_task = h.cleaning_task
    assert paused_task is not None
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED
    assert paused_task.done()

    await h.start_at("One", "test", {})

    assert not h.cleaning_task.done()
    assert h.cleaning_task is not paused_task

@pytest.mark.asyncio
async def test_two_task_interference():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])
    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})

    h.start_cleaning()
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    second_clean = asyncio.get_event_loop().create_task(h.clean_task(delay=0))
    assert abs((datetime.utcnow() - h.cleaning_status["now"] - timedelta(seconds=1)).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - timedelta(seconds=4) - datetime.utcnow()).total_seconds()) < 0.5
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert abs((datetime.utcnow()- h.cleaning_status["now"] - timedelta(seconds=2)).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - timedelta(seconds=3) - datetime.utcnow()).total_seconds()) < 0.5
    assert h.cleaning_task is not None
    assert h.cleaning_task is not second_clean
    assert len(h.active_nodes) == 1
    assert not h.cleaning_task.done()
    assert second_clean.done()


@pytest.mark.asyncio
async def test_clean_past_next_time():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list3.yml"])

    h.register_function(sleep)

    start_time = datetime.utcnow()

    await h.start_at("Two", "test", {})
    await h.start_at("Five", "test", {})
    await h.start_at("Six", "test", {})

    creation_duration = datetime.utcnow()-start_time
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    h.start_cleaning()
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    first_cleaning_task = h.cleaning_task
    await asyncio.sleep(2)
    # next timeout happens now, but now things depend on how long it takes to close nodes. so things should be unchanged now
    assert len(h.active_nodes) == 3
    assert "Two" in [x.graph_node.id for x in h.active_nodes.values()]
    assert "Five" in [x.graph_node.id for x in h.active_nodes.values()]
    assert "Six" in [x.graph_node.id for x in h.active_nodes.values()]
    assert h.cleaning_task is first_cleaning_task
    await asyncio.sleep(1)
    # now the node finishes clearning and some things are changed
    assert h.cleaning_task is not first_cleaning_task
    assert len(h.active_nodes) == 2
    assert "Five" in [x.graph_node.id for x in h.active_nodes.values()]
    assert "Six" in [x.graph_node.id for x in h.active_nodes.values()]