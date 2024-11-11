import yaml
import pytest
import asyncio

import src.DialogHandler as DialogHandler
import src.DialogNodeParsing as DialogParser
import src.DialogNodes.BaseType
import src.BuiltinFuncs.BaseFuncs as BaseFuncs
from src.utils.Enums import POSSIBLE_PURPOSES
import src.utils.CallbackUtils as NodetionCbUtils

GRAPH = '''
nodes:
  - id: node1
    graph_start:
      ping:
    events:
      ping:
        actions:
        - wait: 2
  - id: node2
    graph_start:
      ping:
        session_chaining: start
    events:
      ping:
        actions:
        - wait: 6
'''

@NodetionCbUtils.callback_settings(allowed_purposes=[POSSIBLE_PURPOSES.ACTION, POSSIBLE_PURPOSES.TRANSITION_ACTION], schema={"type": "number"})
async def wait(datapack:NodetionCbUtils.CallbackDatapack):
    time = int(datapack.base_parameter)
    await asyncio.sleep(time)

def test_find_location():
    datapack = NodetionCbUtils.CallbackDatapack(
            active_node="test_AN",
            event={},
            base_parameter="test_param",
            goal_node="test_GN",
            goal_node_name="test_GN_name",
            section_name="test_section_name",
            section_data="test_section_data",
            control_data={}
    )
    assert BaseFuncs.select_from_pack("active_node.timeout", datapack) == "test_AN"
    assert BaseFuncs.select_from_pack("event", datapack) == {}
    assert BaseFuncs.select_from_pack("goal_node", datapack) == "test_GN"
    assert BaseFuncs.select_from_pack("section", datapack) == "test_section_data"

@pytest.mark.asyncio
async def test_saving():
    loadded_yaml = yaml.safe_load_all(GRAPH)
    nodes = DialogParser.parse_contents(loadded_yaml)
    handler = DialogHandler.DialogHandler(name="test", graph_nodes=nodes)
    handler.register_function(wait, {})
    await handler.start_at("node1", "ping", {})
    test_node:src.DialogNodes.BaseType.BaseNode = list(handler.active_node_cache.cache.values())[0]
    datapack = NodetionCbUtils.CallbackDatapack(
            active_node=test_node,
            event={},
            base_parameter="test_param",
            goal_node="test_GN",
            goal_node_name="test_GN_name",
            section_name="test_section_name",
            section_data={},
            control_data={}
    )
    # testing valid save on node
    BaseFuncs.handle_save_data({}, ["active_node.test"], datapack)
    assert "test" in test_node.data
    assert len(test_node.data) == 1
    assert not hasattr(test_node, "test")
    assert test_node.data["test"] == {}

    # assert wrong location doesnt change things
    BaseFuncs.handle_save_data("tester", ["invalid.asdf"], datapack)
    assert "asdf" not in test_node.data
    assert len(test_node.data) == 1
    assert not hasattr(test_node, "asdf")
    assert test_node.data["test"] == {}

    # test saving to another location: section data
    BaseFuncs.handle_save_data("test2", ["section.test2"], datapack)
    assert "test2" not in test_node.data
    assert "test2" in datapack.section_data
    assert not hasattr(test_node, "test2")
    assert datapack.section_data["test2"] == "test2"
    
    # testing invalid save location on node
    BaseFuncs.handle_save_data("test3", ["active_node"], datapack)
    assert "test3" not in test_node.data
    assert len(test_node.data) == 1
    assert not hasattr(test_node, "test3")

    # testing setting timeout on node
    BaseFuncs.handle_save_data(None, ["active_node.timeout"], datapack)
    assert test_node.timeout is None

    # testing setting nested structure
    BaseFuncs.handle_save_data("tester", ["active_node.test.nest"], datapack)
    assert "nest" in test_node.data["test"]
    assert len(test_node.data["test"]) == 1
    assert test_node.data["test"]["nest"] == "tester"