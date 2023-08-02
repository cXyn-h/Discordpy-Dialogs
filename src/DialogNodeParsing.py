import yaml
import copy

import logging
import sys

import src.DialogNodes.BaseNode as BaseType

#TODO: future: autoimport nodes from folder?

dialog_logger = logging.getLogger('Dialog Handler')

ALLOWED_GRAPH_NODES = {"Base":BaseType}
'''list of modules allowed to be used in graph'''
NODE_DEFINITION_CACHE = {"Base": yaml.safe_load(BaseType.GraphNode.DEFINITION)}

def register_node(type_module):
    if not hasattr(type_module,"GraphNode"):
        raise Exception(f"trying to register node type but module does not have identifiable GraphNode class.")
    # maybe duck type this instead
    # if not issubclass(type_module.GraphNode, BaseType.GraphNode):
    #     raise Exception(f"module does not have valid Graphnode definition, not subclass of base Graph node")
    if not hasattr(type_module, "Node"):
        raise Exception(f"trying to register node type but module does not have identifiable Node class.")
    if type_module.GraphNode.TYPE in ALLOWED_GRAPH_NODES:
        dialog_logger.info(f"type {type_module.GraphNode.TYPE} already registered, skipping")
    ALLOWED_GRAPH_NODES[type_module.GraphNode.TYPE] = type_module

def parse_version_string(version_string):
    '''takes version string and returns tuple of three numbers representing version number
    Parameters
    ----
    version_string - `str`
        string of of three ints separated by periods
    Return
    ---
    tuple'''
    first_dot=version_string.find(".")
    if first_dot < 0:
        raise Exception(f"{version_string} is invalid version, must have three period separated numbers")
    second_dot=version_string.find(".",first_dot+1)
    if second_dot < 0:
        raise Exception(f"{version_string} is invalid version, must have three period separated numbers")
    try:
        version_tuple=(int(version_string[:first_dot]),int(version_string[first_dot+1:second_dot]), int(version_string[second_dot+1:]))
    except:
        raise Exception(f"{version_string} is invalid version, must have three period separated numbers")
    return version_tuple

def parse_files(*file_names, existing_nodes = {}):
    '''parses list of files for nodes and appends them onto existing nodes, raising error if already there'''
    dialog_logger.debug(f"loading files {file_names}, with existing nodes {existing_nodes}")
    final_node_list = existing_nodes
    for file_name in file_names:
        parse_file(file_name, final_node_list)
    return final_node_list

def parse_file(file_name, existing_nodes={}):
    final_node_list = existing_nodes
    with open(file_name) as file:
        doc_dict = yaml.safe_load_all(file)
        for doc_ind, yaml_doc in enumerate(doc_dict):
            dialog_logger.debug(f"parsing document indexed {doc_ind} from file '{file_name}'")
            if "nodes" not in yaml_doc or len(yaml_doc["nodes"]) == 0:
                dialog_logger.debug(f"file {file_name} document indexed {doc_ind} does not have list of nodes, moving to next")
                continue
            
            for node_ind,yaml_node in enumerate(yaml_doc["nodes"]):
                dialog_logger.debug(f"parsing node: file '{file_name}' doc: {doc_ind} node: {node_ind}")
                try:
                    node = parse_node(yaml_node)
                    dialog_logger.debug(f"parsed node is {node.id}, existing are {final_node_list.keys()}")
                except Exception as e:
                    raise Exception(f"Exception at file {file_name} doc {doc_ind} node {node_ind}, details: {e}")
                if node.id in final_node_list:
                    raise Exception(f"node {node.id} has been redefined at file {file_name} doc {doc_ind} node {node_ind}")
                final_node_list[node.id] = node
    dialog_logger.info(f"finished loading file {file_name}, found <{len(final_node_list)}> nodes")
    # dialog_logger.debug("nodes: %s", final_node_list)
    return final_node_list

def parse_node(yaml_node):
    node_type = "Base"
    if "type" in yaml_node:
        if yaml_node["type"] not in ALLOWED_GRAPH_NODES.keys():
            raise Exception(f"{yaml_node['type']} is unknown type")
        node_type = yaml_node["type"]
    # node_type should be filled at this point, either Base or listed type
    # type is known, make sure definition already parsed as well
    if node_type not in NODE_DEFINITION_CACHE:
        try:
            NODE_DEFINITION_CACHE[node_type] = yaml.safe_load(ALLOWED_GRAPH_NODES[node_type].GraphNode.DEFINITION)
        except Exception as e:
            raise Exception(f"tried to read node definition of '{node_type}' but couldn't. details: {e}")
    
    # have version label is here, but not fully checked/used
    node_version = None
    if "version" in yaml_node:
        node_version = yaml_node["version"]
    elif "v" in yaml_node:
        node_version = yaml_node["v"]
    
    if not node_version:
        dialog_logger.warning(f"node found without version, assuming most recent of {ALLOWED_GRAPH_NODES[node_type].GraphNode.VERSION}")
        node_version = ALLOWED_GRAPH_NODES[node_type].GraphNode.VERSION

    actual_version = parse_version_string(node_version)
    target_version = parse_version_string(ALLOWED_GRAPH_NODES[node_type].GraphNode.VERSION)
    if actual_version[0] != target_version[0]:
        raise Exception(f"node version is too different from what is being used, please update yaml definition")
    # more checking version mismatches?

    all_options = [*NODE_DEFINITION_CACHE["Base"]["options"]]
    if node_type != "Base":
        all_options.extend(NODE_DEFINITION_CACHE[node_type]["options"])

    graph_node_model = {}
    for option in all_options:
        if option["presence"] == "required" and option["name"] not in yaml_node:
                raise Exception(f"field {option['name']} not fond in node")
        if option["name"] not in yaml_node:
            if "default" not in option:
                raise Exception(f"found optional value '{option['name']}' missing fron yaml and no default value specified")
            graph_node_model[option["name"]] = copy.deepcopy(option["default"])
        else:
            graph_node_model[option["name"]] = yaml_node[option["name"]]
            #TODO: soon-future: Parsing callbacks, filters, events etc
    ALLOWED_GRAPH_NODES[node_type].GraphNode.verify_format_data(graph_node_model)

    return ALLOWED_GRAPH_NODES[node_type].GraphNode(graph_node_model)

def validate_format():
    #TODO: future QOL expansion
    pass