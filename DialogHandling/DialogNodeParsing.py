''' file containing methods for parsing nodes from dictionaries. These functions are for processing cases that might need 
    different formatting from what comes in. only parse_node is meant to be called from outside this file'''
from DialogHandling.DialogObjects import *
from discord import TextStyle

# node_types={"dialog":DialogInfo, "modal":ModalInfo, "reply":ReplyNodeInfo}
node_types = ["dialog", "modal", "reply"]

#TODO: extensive testing of this and format guards
#TODO: forbid reply to modal transition, and other impossible overarching stuff

def parse_node(yaml_node):
    '''creates the Info object for node, and any defined nested inside this node. raises exception when data is missing

    Return
    ---
    tuple, first element is this node that was passed in, second is list of node definitions that were found nested
    '''
    nested_definitions = []
    if (not "id" in yaml_node):
        # basically all loaded nodes must have a id
        raise Exception("node missing id: "+ str(yaml_node) if len(str(yaml_node)) < 70 else str(yaml_node)[:35]+ "..."+str(yaml_node)[-35:])

    node_type = "dialog"
    if "type" in yaml_node:
        if not yaml_node["type"] in node_types:
            raise Exception("unkown type for node "+ yaml_node["id"]+" defintion: "+ str(yaml_node) if len(str(yaml_node)) < 70 else str(yaml_node)[:35]+ "..."+str(yaml_node)[-35:])
        node_type = yaml_node["type"]
    
    # yaml definition needs a type flag to specify if it is not a dialog node
    if node_type == "modal":
        if (not "title" in yaml_node):
            # basically all modals must have a separate title to display to all interacters
            raise Exception("modal node missing title "+str(yaml_node))

        if "options" in yaml_node:
            print("modal node", yaml_node["id"],"definition has options defined in it. Note this will be ignored")

        fields = {}
        if "fields" in yaml_node:
            for yaml_field in yaml_node["fields"]:
                if (not "label" in yaml_field) or (not "id" in yaml_field):
                    raise Exception("modal node \""+yaml_node["id"]+"\" has mis formed field" + yaml_field )
                if yaml_field["id"] in fields:
                    raise Exception("field \""+yaml_field["id"]+"\" already defined for modal node \"" + yaml_node["id"] + "\"")
                if "style" in yaml_field:
                    if yaml_field["style"] == "paragraph":
                        yaml_field["style"] = TextStyle.paragraph
                    elif yaml_field["style"] == "long":
                        yaml_field["style"] = TextStyle.paragraph
                    else:
                        yaml_field["style"] = TextStyle.short
                fields[yaml_field["id"]] = ModalFieldInfo(yaml_field)
        if len(fields) < 1 or len(fields) > 5:
            raise Exception(f"modal {yaml_node['id']} has wrong number of fields, must be between 1 and 5, but currently has {len(fields)}")
    
        if "next_node" in yaml_node:
            next_id, next_nested_nodes = parse_next_node_field(yaml_node["next_node"])
            nested_definitions.extend(next_nested_nodes)
            yaml_node["next_node"] = next_id
        return (ModalInfo({**yaml_node, "fields":fields}), nested_definitions)

    elif node_type == "reply":
        if "next_node" in yaml_node:
            next_id, next_nested_nodes = parse_next_node_field(yaml_node["next_node"])
            nested_definitions.extend(next_nested_nodes)
            yaml_node["next_node"] = next_id
        return (ReplyNodeInfo(yaml_node),nested_definitions)
    else:
        # assuming if not labeled or otherwise labeled incorrectly, is a dialog. 
        if (not "prompt" in yaml_node):
            # currently requiring all dialog nodes need a prompt
            raise Exception("dialog node missing prompt: "+ str(yaml_node))

        if "fields" in yaml_node:
            print("dialog node definition has fields defined in it. Note this will be ignored")

        options = {}
        # ensure any options for this dialog are loaded correctly before saving dialog
        if "options" in yaml_node:
            for yaml_option in yaml_node["options"]:
                loaded_option, option_nested = parse_option_field(yaml_option, yaml_node)
                nested_definitions.extend(option_nested)
                if loaded_option.id in options:
                    raise Exception("option \""+loaded_option.id+"\" already defined for dialog node \""+yaml_node["id"]+"\"")
                options[loaded_option.id] = loaded_option
        return (DialogInfo({**yaml_node, "options":options}), nested_definitions)

def parse_option_field(yaml_option, yaml_parent_dialog):
    ''' creates and returns OptionInfo object to hold option data. raises exceptions when data is missing and adds 
            any in-line definitions for nodes to the handler'''
    nested_definitions=[]
    if (not "label" in yaml_option) or (not "id" in yaml_option):
        raise Exception("option missing label or id"+ str(yaml_option))
    
    if "next_node" in yaml_option:
        next_id, next_nested_nodes = parse_next_node_field(yaml_option["next_node"])
        nested_definitions.extend(next_nested_nodes)
        yaml_option["next_node"] = next_id
    return (OptionInfo(yaml_option), nested_definitions)

def parse_next_node_field(next_field):
    '''parses the next_node field. returns tuple of next node id and any nested node definitions including the one named as next'''
    if next_field is None:
        raise Exception("next field is not defined")
    if type(next_field) is str:
        return (next_field,[])
    nested_definitions = []
    next_node, next_nested = parse_node(next_field)
    nested_definitions.append(next_node)
    nested_definitions.extend(next_nested)
    return (next_node.id, nested_definitions)