''' file containing methods for parsing layout nodes from dictionaries. Layout nodes are data storing objects defining common operations and paths
    to take, the class is the blueprint for a type of node.
    parse_node is the entry point, all other methods are helpers for parsing specific fields that are stored in a different format than what
    comes in from the yanl reading.'''
import DialogHandling.DialogObjects as DialogObjects
import DialogHandling.BuiltinNodeDefinitions.DialogNode as DialogNodeDefinitions
import DialogHandling.BuiltinNodeDefinitions.ModalNode as ModalNodeDefinitions
import DialogHandling.BuiltinNodeDefinitions.MessageReplyNode as ReplyNodeDefinitions
import DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions

node_types={"dialog":DialogNodeDefinitions.DialogLayout, "modal":ModalNodeDefinitions.ModalLayout, "reply":ReplyNodeDefinitions.ReplyLayout}


def register_node_type(NodeLayout):
    if not hasattr(NodeLayout, "type"):
        raise Exception(f"Trying to register node layout {NodeLayout.type} but it is badly defined. missing 'type' attribute")
    elif NodeLayout.type == BaseNodeDefinitions.BaseLayout.type:
        raise Exception(f"Trying to register node layout {NodeLayout.type} but it hasn't been changed from base node's. Please choose a unique one")
    if NodeLayout.type in node_types and NodeLayout != node_types[NodeLayout.type]:
        raise Exception(f"Trying to register node layout {NodeLayout.type} but it is already registered with a different class")
    node_types[NodeLayout.type] = NodeLayout

#TODO: soon: extensive testing of this and format guards
#TODO: soon: forbid reply to modal transition, and other impossible overarching stuff
def parse_node(yaml_node):
    '''entry point of parsing a node. This method does the starting steps of making sure fields required for all nodes are there
    and identifies which node type it is to continue parsing. Each different type of node is responsible for parsing itself and returning
    the layout node and any nodes whose definitions were nested inside.

    Parameters
    ---
    `yaml_node` - dictionary
        dictionary holding the fields and values for a node. double check that the type of node in this dictionary is in node_types

    Raises
    ---
    Exception when node definition is missing elements, malformed, or has duplicate definitions when it cannot have it or node type is not found. 
    Each type of node is responsible for throwing exceptions when it is malformed, and any program calling this method is responsible for 
    any catching needed

    Returns
    ---
    tuple, first element is the layout node object for the definition that was passed in, second is list of layout nodes whose definitions
    were found nested inside. Recommend passing each nested definition to DialogNodeParsing.parse_node to take care of. Be sure to go through and 
    check for duplicate node definitions 
    '''
    if (not "id" in yaml_node):
        # basically all loaded nodes must have a id
        raise Exception("node missing id: "+ str(yaml_node) if len(str(yaml_node)) < 70 else str(yaml_node)[:35]+ "..."+str(yaml_node)[-35:])

    # yaml definition needs a type flag to specify if it is not a dialog node
    node_type = "dialog"
    if "type" in yaml_node:
        if not yaml_node["type"] in node_types.keys():
            raise Exception("unkown type for node "+ yaml_node["id"]+" defintion: "+ str(yaml_node) if len(str(yaml_node)) < 70 else str(yaml_node)[:35]+ "..."+str(yaml_node)[-35:])
        node_type = yaml_node["type"]

    return node_types[node_type].parse_node(yaml_node)
    
def parse_option_field(yaml_option, yaml_parent_dialog):
    '''creates and returns OptionInfo object to hold option data. Meant to represent a path to be chosen through a discord component button.

    Returns
    ---
    tuple - first is the OptionInfo object, the second is list of layout nodes whose definitions were found nested inside the option. 
    Recommend passing each nested definition to DialogNodeParsing.parse_node to take care of. Be sure to go through and check for 
    duplicate node definitions
    '''
    nested_definitions=[]
    if (not "label" in yaml_option) or (not "id" in yaml_option):
        raise Exception("option missing label or id"+ str(yaml_option))
    
    if "next_node" in yaml_option:
        next_id, next_nested_nodes = parse_next_node_field(yaml_option["next_node"])
        nested_definitions.extend(next_nested_nodes)
        yaml_option["next_node"] = next_id
    return (DialogObjects.OptionInfo(yaml_option), nested_definitions)

def parse_next_node_field(next_field):
    '''parses the next_node field. Layout nodes are exepected to have id of next node in this field, but yaml files could nest a node definition
        in this field. 

    Parameter
    ---
    `next_field` - str or dictionary
        id of next node to go to or dictionary because its definition was nested inside
    
    Returns
    ---
     tuple of next node id and any nested node definitions including the one named as next'''
    if next_field is None:
        raise Exception("next field is not defined")
    if type(next_field) is str:
        return (next_field,[])
    nested_definitions = []
    next_node, next_nested = parse_node(next_field)
    nested_definitions.append(next_node)
    nested_definitions.extend(next_nested)
    return (next_node.id, nested_definitions)