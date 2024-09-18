import pytest
import Tests.Test_Old_cache.Cache_old as Cache_old
import src.DialogNodes.BaseType as BaseType
from Tests.Test_Old_cache.CacheNodeIndex import CacheNodeIndex
import src.DialogNodeParsing as NodeParser
import yaml

def test_add_nodes():
    simple_input='''
id: One
TTL: 300'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))
    simple_input2='''
id: Two'''
    loaded_node2 = NodeParser.parse_node(yaml.safe_load(simple_input2))

    c = Cache_old.Cache()

    c.add("One", loaded_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert "One" in c.data
    assert type(c.data["One"]) is BaseType.BaseGraphNode
    # tests for node has good data is from parsing tests

    assert c.data["One"] is loaded_node
    assert c.get("One", override_copy_rule=Cache_old.COPY_RULES.ORIGINAL)[0] is loaded_node
    assert c.data["One"].timeout == loaded_node.timeout
    assert c.data["One"].id == loaded_node.id
    assert c.data["One"].graph_start == loaded_node.graph_start
    assert c.data["One"].primary_key == loaded_node.primary_key
    assert c.data["One"].secondary_keys is loaded_node.secondary_keys

    c.add("Two", loaded_node2, addition_copy_rule=Cache_old.COPY_RULES.SHALLOW)
    assert c.data["Two"].timeout == loaded_node2.timeout
    assert c.data["Two"].id == loaded_node2.id
    assert c.data["Two"].graph_start == loaded_node2.graph_start
    assert c.data["Two"].primary_key == loaded_node2.primary_key
    assert c.data["Two"].secondary_keys is not loaded_node.secondary_keys

    retrieved_one = c.get("One", override_copy_rule=Cache_old.COPY_RULES.DEEP)[0]
    assert retrieved_one.timeout == loaded_node.timeout
    assert retrieved_one.graph_start == loaded_node.graph_start
    assert retrieved_one.primary_key == loaded_node.primary_key
    assert retrieved_one.secondary_keys is not loaded_node.secondary_keys

def test_add_or_overwrite():
    simple_input='''
id: One
TTL: 300'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

    c = Cache_old.Cache()

    c.add("One", loaded_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert "One" in c.data
    
    c.add("One", loaded_node, or_overwrite=False, addition_copy_rule=Cache_old.COPY_RULES.SHALLOW)
    assert "One" in c.data
    assert c.data["One"] is loaded_node

    # currently no implementation for setting or updating values in Nodes
    result = c.add("One", loaded_node, or_overwrite=True, addition_copy_rule=Cache_old.COPY_RULES.SHALLOW)
    assert result is not None
    assert "One" in c.data
    assert c.data["One"] is loaded_node

def test_delete_node():
    simple_input='''
id: One
TTL: 300'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(simple_input))

    c = Cache_old.Cache()

    c.add("One", loaded_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert "One" in c.data
    loaded_node.cache is c

    c.delete("One")
    assert "One" not in c.data
    assert loaded_node.cache is None

def test_index_add_active():
    input1='''
id: One
events:
    event1:
    event2:
    event3:'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(input1))

    active_node = BaseType.BaseNode(loaded_node)

    c = Cache_old.Cache(input_secondary_indices=[CacheNodeIndex("events", "event")])

    c.add(id(active_node), active_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert c.secondary_indices["events"].pointers == {"event1": set([id(active_node)]), "event2": set([id(active_node)]), "event3": set([id(active_node)])}
    assert c.data[id(active_node)].secondary_keys == {"events": ["event1", "event2", "event3"]}

def test_index_delete_active():
    input1='''
id: One
events:
    event1:
    event2:
    event3:'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(input1))
    active_node = BaseType.BaseNode(loaded_node)

    c = Cache_old.Cache(input_secondary_indices=[CacheNodeIndex("events", "event")])

    c.add(id(active_node), active_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)
    assert c.secondary_indices["events"].pointers == {"event1": set([id(active_node)]), "event2": set([id(active_node)]), "event3": set([id(active_node)])}
    assert c.data[id(active_node)].secondary_keys == {"events": ["event1", "event2", "event3"]}

    c.delete(id(active_node))
    assert c.secondary_indices["events"].pointers == {}
    assert active_node.secondary_keys == {"events": ["event1", "event2", "event3"]}

def test_reindex():
    input1='''
id: One
events:
    event1:
    event2:
    event3:'''
    loaded_node = NodeParser.parse_node(yaml.safe_load(input1))
    active_node = BaseType.BaseNode(loaded_node)

    index = CacheNodeIndex("events", "event")

    c = Cache_old.Cache()

    # add before index is there to simulate changes in data
    c.add(id(active_node), active_node, addition_copy_rule=Cache_old.COPY_RULES.ORIGINAL)

    # this will not update things correctly, but link them together which is only good for testing
    index.cache = c
    c.secondary_indices["events"] = index
    assert c.secondary_indices["events"].pointers == {}

    c.reindex()
    assert c.secondary_indices["events"].pointers == {"event1": set([id(active_node)]), "event2": set([id(active_node)]), "event3": set([id(active_node)])}
    assert c.data[id(active_node)].secondary_keys == {"events": ["event1", "event2", "event3"]}

    # make sure reindex picks up changes correctly
    del loaded_node.events["event3"]
    assert c.secondary_indices["events"].pointers == {"event1": set([id(active_node)]), "event2": set([id(active_node)]), "event3": set([id(active_node)])}
    assert c.data[id(active_node)].secondary_keys == {"events": ["event1", "event2", "event3"]}

    c.secondary_indices["events"].reindex()
    assert c.secondary_indices["events"].pointers == {"event1": set([id(active_node)]), "event2": set([id(active_node)])}
    assert c.data[id(active_node)].secondary_keys == {"events": ["event1", "event2"]}

#TODO: add testing index on item update/set if/when updating nodes is supported