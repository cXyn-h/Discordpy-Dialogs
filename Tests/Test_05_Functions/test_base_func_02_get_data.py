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

@pytest.mark.asyncio
async def test_get_data():
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
    # adding valid save on node
    BaseFuncs.handle_save_data({}, ["active_node.test"], datapack)
    assert "test" in test_node.data
    assert len(test_node.data) == 1
    assert not hasattr(test_node, "test")
    assert test_node.data["test"] == {}

    # adding setting nested structure
    BaseFuncs.handle_save_data("tester", ["active_node.test.nest"], datapack)
    assert "nest" in test_node.data["test"]
    assert len(test_node.data["test"]) == 1
    assert test_node.data["test"]["nest"] == "tester"

    assert BaseFuncs.get_data(datapack, "active_node.test.nest", None) == "tester"
    assert BaseFuncs.get_data(datapack, "active_node.test", None) == {"nest": "tester"}
    assert BaseFuncs.get_data(datapack, "active_node.graph_node", None) is test_node.graph_node
