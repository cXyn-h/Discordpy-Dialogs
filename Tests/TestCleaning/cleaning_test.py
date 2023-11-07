import src.DialogHandler as DialogHandler
import src.DialogNodeParsing as DialogParser
import src.utils.callbackUtils as cbUtils
from src.utils.Enums import POSSIBLE_PURPOSES, CLEANING_STATE, ITEM_STATUS
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

@cbUtils.callback_settings(allowed_sections=[POSSIBLE_PURPOSES.ACTION], has_parameter="always")
async def sleep(active_node, event, duration, occurance_tracker={}):
    if id(active_node) not in occurance_tracker:
        occurance_tracker[id(active_node)] = "started"
        clean_test_logger.debug(f"custom callback occurance tracker calling for first time on <{id(active_node)}>")
    else:
        if occurance_tracker[id(active_node)] == "started":
            clean_test_logger.error(f"callback called multiple times on same node <{id(active_node)}>, incomplete call last time")
            raise Exception(f"callback called multiple times on same node <{id(active_node)}>, incomplete call last time")
        else:
            clean_test_logger.debug(f"custom callback occurance tracker sees double call on <{id(active_node)}> but callback finished last time")
    clean_test_logger.debug(f"sleep close callback called, node is {id(active_node)} {active_node.graph_node.id} sleepign for {duration}")
    await asyncio.sleep(duration)
    clean_test_logger.debug(f"sleep close callback for node {id(active_node)} {active_node.graph_node.id} done")
    occurance_tracker[id(active_node)] = "finished"

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
async def test_clean_info_finds_timed_out_closing_node():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list1.yml"])

    await h.start_at("One", "test", {})
    act_node_one = [x for x in h.active_nodes.values() if x.graph_node.id == "One"][0]
    await h.start_at("Two", "test", {})
    now = datetime.utcnow()

    act_node_one.notify_closing()
    
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    timed_out_nodes, timed_out_sessions, next_time = h.get_timed_out_info()
    assert next_time is not None
    assert abs((next_time - now).total_seconds() - 50) < 0.5
    assert len(timed_out_nodes) == 1
    assert timed_out_nodes[0].graph_node.id == "One"

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
    assert abs((h.cleaning_status["next"] - start_time).total_seconds()) < 0.5

@pytest.mark.asyncio
async def test_one_clean_is_right():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})
    # node one times out now, two times out in 5 seconds
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    start_time = datetime.utcnow()
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    assert len(h.active_nodes) == 2
    await asyncio.sleep(0.5)
    # let cleaning actually start, make sure is recorded as such and now is this cycle and next is correct for node two
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert abs((h.cleaning_status["now"] - start_time).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - start_time - timedelta(seconds=5)).total_seconds()) < 0.5
    assert len(h.active_nodes) == 1
    assert "Two" in [x.graph_node.id for x in h.active_nodes.values()]
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    # at this point clean task finished this round and is sleeping for next round (longer sleep) and state won't change until it wakes up again
    await asyncio.sleep(5)
    assert len(h.active_nodes) == 0
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED

@pytest.mark.asyncio
async def test_stop_clean():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})

    # node one times out now, two times out in 5 seconds
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    start_time = datetime.utcnow()
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    assert len(h.active_nodes) == 2
    await asyncio.sleep(0.5)
    # let cleaning actually start, make sure is recorded as such and now is this cycle and next is correct for node two
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert abs((h.cleaning_status["now"] - start_time).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - start_time - timedelta(seconds=5)).total_seconds()) < 0.5
    res = h.stop_cleaning()
    assert res == True
    assert len(h.active_nodes) == 1
    assert "Two" in [x.graph_node.id for x in h.active_nodes.values()]
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPING
    # at this point clean task finished this round and is sleeping for next round (longer sleep) and state won't change until it wakes up again
    await asyncio.sleep(5)
    assert len(h.active_nodes) == 1
    assert "Two" in [x.graph_node.id for x in h.active_nodes.values()]
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

    # timeouts are 0, 5, 10, 15 respectively. doing large just to make sure it always has a next time while this test is running

    creation_duration = datetime.utcnow()-start_time
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    # first start should always work
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    first_cleaning_task = h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    # reattempt to start when cleaning task hasn't had a chance to run should fail, but task should remain unchanged
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert first_cleaning_task is h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    await asyncio.sleep(1)
    # after giving chance to run, task should be same but now running. start attempt fail since already running
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert first_cleaning_task is h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING

@pytest.mark.asyncio
async def test_repeat_clean_starts_empty():
    h = DialogHandler.DialogHandler()

    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    # first start attempt should work as always. creates task
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    first_cleaning_task = h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    # no matter what list, immediate attempt to restart should fail but not change anything
    started = h.start_cleaning()
    assert started == False
    assert h.cleaning_task is not None
    assert first_cleaning_task is h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING
    await asyncio.sleep(1)
    # after given a chance to run clean task, should go to paused since no next nodes no active cleaning needed
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED
    # cleaning should be startable. (otherwise pause would be more of a stop). task would have finished when pausing tho so new task
    started = h.start_cleaning()
    assert started == True
    assert h.cleaning_task is not None
    assert first_cleaning_task is not h.cleaning_task
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING


@pytest.mark.asyncio
async def test_clean_should_never_run():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])

    # lots of tests here using node One as the one that times out first clean.
    await h.start_at("One", "test", {})

    start_time = datetime.utcnow()
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    # invalid start of task, needs to be in STARTING or RUNNING state
    h.cleaning_task = asyncio.get_event_loop().create_task(h.clean_task(delay=0))
    counter = 0
    while not h.cleaning_task.done() and counter < 20:
        assert h.cleaning_status["state"] != CLEANING_STATE.RUNNING
        await asyncio.sleep(1)
        counter += 1
    if counter == 20:
        assert "might be long running clean, or other weirdness" == "fix that"
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
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
    assert h.cleaning_status["state"] == CLEANING_STATE.STARTING

@pytest.mark.asyncio
async def test_two_task_interference():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list2.yml"])
    await h.start_at("One", "test", {})
    await h.start_at("Two", "test", {})

    h.start_cleaning()
    # node One times out now, Two times out in 5 seconds
    await asyncio.sleep(0.5)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    first_clean = h.cleaning_task
    second_clean = asyncio.get_event_loop().create_task(h.clean_task(delay=0))
    assert abs((datetime.utcnow() - h.cleaning_status["now"] - timedelta(seconds=0.5)).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - datetime.utcnow() - timedelta(seconds=4.5)).total_seconds()) < 0.5
    await asyncio.sleep(1)
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert abs((datetime.utcnow() - h.cleaning_status["now"] - timedelta(seconds=1.5)).total_seconds()) < 0.5
    assert abs((h.cleaning_status["next"] - timedelta(seconds=3.5) - datetime.utcnow()).total_seconds()) < 0.5
    assert h.cleaning_task is not None
    assert h.cleaning_task is not second_clean
    assert len(h.active_nodes) == 1
    assert not h.cleaning_task.done()
    assert second_clean.done()

@pytest.mark.asyncio
async def test_clean_past_next_time():
    '''testing cleaning going long over time to do next clean. without outside interference'''
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list3.yml"])

    h.register_function(sleep)

    start_time = datetime.utcnow()

    await h.start_at("Two", "test", {})
    act_node_two_one = [x for x in h.active_nodes.values() if x.graph_node.id == "Two"][0]
    await h.start_at("Five", "test", {})
    act_node_five_one = [x for x in h.active_nodes.values() if x.graph_node.id == "Five"][0]

    creation_duration = datetime.utcnow()-start_time
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    h.start_cleaning()
    # node Two immediate timeout, Five to timeout in 3 from now
    await asyncio.sleep(0.5)
    # cleaning started, node Two clean takes 4 seconds (3.5 seconds from now) which is when next round will occur
    assert act_node_two_one.status == ITEM_STATUS.CLOSING
    assert act_node_five_one.status == ITEM_STATUS.ACTIVE
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert id(act_node_two_one) in h.active_nodes
    assert id(act_node_five_one) in h.active_nodes
    assert act_node_five_one.handler is h
    assert act_node_two_one.handler is h
    first_cleaning_task = h.cleaning_task
    await asyncio.sleep(3)
    # five supposed to time out now, but still 0.5 more second on cleaning previous node
    assert act_node_two_one.status == ITEM_STATUS.CLOSING
    assert act_node_five_one.status == ITEM_STATUS.ACTIVE
    assert not first_cleaning_task.done()
    assert h.cleaning_task is first_cleaning_task
    await asyncio.sleep(1)
    # at this point cleaning for node finishes and cleaning refreshes and five starts cleaning now
    assert act_node_two_one.status == ITEM_STATUS.CLOSED
    assert act_node_five_one.status == ITEM_STATUS.CLOSING
    assert h.cleaning_task is not first_cleaning_task
    second_cleaning_task = h.cleaning_task
    assert first_cleaning_task.done()
    await asyncio.sleep(1)
    assert act_node_five_one.status == ITEM_STATUS.CLOSING
    await asyncio.sleep(1)
    assert act_node_five_one.status == ITEM_STATUS.CLOSED
    assert second_cleaning_task.done()
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED

@pytest.mark.asyncio
async def test_clean_list_overlap():
    h = DialogHandler.DialogHandler()
    h.setup_from_files(["Tests/TestCLeaning/node_list3.yml"])

    h.register_function(sleep)

    start_time = datetime.utcnow()

    await h.start_at("Two", "test", {})
    act_node_two_one = [x for x in h.active_nodes.values() if x.graph_node.id == "Two"][0]
    await h.start_at("Two", "test", {})
    act_node_two_two = [x for x in h.active_nodes.values() if x.graph_node.id == "Two" and x is not act_node_two_one][0]
    assert id(act_node_two_one) != id(act_node_two_two)
    await h.start_at("Five", "test", {})
    act_node_five_one = [x for x in h.active_nodes.values() if x.graph_node.id == "Five"][0]

    creation_duration = datetime.utcnow()-start_time
    assert h.cleaning_status["state"] == CLEANING_STATE.STOPPED
    h.start_cleaning()
    # node Two immediate timeout, Five to timeout in 3 from now
    await asyncio.sleep(0.5)
    # cleaning started, node Two clean takes 4 seconds (3.5 seconds from now) which is when next round will occur
    assert act_node_two_one.status == ITEM_STATUS.CLOSING
    assert act_node_two_two.status == ITEM_STATUS.ACTIVE
    assert act_node_five_one.status == ITEM_STATUS.ACTIVE
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert id(act_node_two_one) in h.active_nodes
    assert id(act_node_five_one) in h.active_nodes
    assert act_node_five_one.handler is h
    assert act_node_two_one.handler is h
    first_cleaning_task = h.cleaning_task
    await asyncio.sleep(3)
    # now timeout has happened, but long clean still going
    assert act_node_two_one.status == ITEM_STATUS.CLOSING
    assert act_node_two_two.status == ITEM_STATUS.ACTIVE
    assert act_node_five_one.status == ITEM_STATUS.ACTIVE
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert len(h.active_nodes) == 3
    await asyncio.sleep(1)
    # cleaning finished prev node, starting task again cause going over
    # node five takes 2 seconds to closed, two takes four
    assert act_node_two_one.status == ITEM_STATUS.CLOSED
    assert h.cleaning_task is not first_cleaning_task
    second_cleaning_task = h.cleaning_task
    assert not first_cleaning_task.done()

    # keeping first task around after being demoted to just finish what it's got. it goes to start cleaning its next node before main task starts
    # so first task cleans node two, main one gets five
    assert act_node_five_one.status == ITEM_STATUS.CLOSING
    assert act_node_two_two.status == ITEM_STATUS.CLOSING
    assert h.cleaning_status["state"] == CLEANING_STATE.RUNNING
    assert len(h.active_nodes) == 2
    await asyncio.sleep(2)
    # five finished cleaning, two still going.
    assert act_node_five_one.status == ITEM_STATUS.CLOSED
    assert act_node_two_two.status == ITEM_STATUS.CLOSING
    assert not first_cleaning_task.done()
    assert len(h.active_nodes) == 1
    assert h.cleaning_status["state"] == CLEANING_STATE.PAUSED
    await asyncio.sleep(2)
    assert act_node_two_two.status == ITEM_STATUS.CLOSED
    assert first_cleaning_task.done()
    assert len(h.active_nodes) == 0
