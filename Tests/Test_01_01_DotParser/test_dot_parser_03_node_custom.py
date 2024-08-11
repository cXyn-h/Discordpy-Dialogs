import src.utils.DotNotator as DotNotator
from src.DialogNodes.BaseType import BaseGraphNode, BaseNode
import src.DialogNodeParsing as NodeParser
import yaml

node_def = '''
id: test
type: Base
version: "3.8.0"
close_actions:
- delete
actions:
- prep
- send
events:
  post_event:
    actions:
    - respond
    transitions:
    - node_names:
        handle_post: 1
        test: 2
  delete_event:
    transitions:
    - node_names:
        test2: 1
      transition_actions:
      - prep_transition
'''

def test_Base_custom_regular():
    '''test to make sure indexer works with things that aren't special cases to handle'''
    loaded_node_01 = NodeParser.parse_node(yaml.safe_load(node_def))
    assert DotNotator.parse_dot_notation(["TYPE"], loaded_node_01) == "Base"
    assert DotNotator.parse_dot_notation(["VERSION"], loaded_node_01) == "3.8.0"

def test_Base_custom_special():
    loaded_node_01 = NodeParser.parse_node(yaml.safe_load(node_def))
    functions_result = DotNotator.parse_dot_notation(["functions"], loaded_node_01, custom_func_name="indexer")
    assert isinstance(functions_result, list)
    functions_result.sort()
    assert functions_result == ["delete", "prep", "prep_transition", "respond", "send"]

    #disabled for node v3.8.0
    # next_nodes_result = DotNotator.parse_dot_notation(["next_nodes"], loaded_node_01, custom_func_name="indexer")
    # assert isinstance(next_nodes_result, list)
    # next_nodes_result.sort()
    # assert next_nodes_result == ["handle_post", "test", "test2"]