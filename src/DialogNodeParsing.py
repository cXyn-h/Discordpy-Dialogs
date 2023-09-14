import yaml
import copy
import inspect
import logging

import src.DialogNodes.BaseType as BaseType
import src.utils.LoggingHelper as logHelper

# for validing yaml in right format. why *JSON*schema? because it validates based on read in dictionaries. Once yaml is read in there's no difference
from jsonschema import validate, ValidationError

#TODO: future: autoimport nodes from folder?
#TODO: future QoL: allowing node types to extend from non Base type nodes

parsing_logger = logging.getLogger('Dialog Parser')
logHelper.use_default_setup(parsing_logger)
parsing_logger.setLevel(logging.INFO)

#TODO: this allows globally, any instances of needing to limit to subsets? -ie would this need to be in a class
ALLOWED_NODE_TYPES = {}
'''list of node types that the parser can handle'''
NODE_DEFINITION_CACHE = {}
'''temp store of parsed definition for node types, type must appear in ALOWED_NODE_TYPES, read in as string, cached as dict'''
NODE_SCHEMA_CACHE = {}
'''temp store of parsed schema for node types, type must appear in ALLOWED_NODE_TYPES, read in as string, cached as dict'''
#~~~~~~~~~ FURTHER SETUP OF THESE ARE DONE AFTER DEFINING FUNCTIONS FOR HANDLING AND REGESTERING ~~~~~~~~~

def register_node_type(type_module, type_name, re_register = False):
    '''validates and registers a node type that the parser can use. Raises Exceptions for invalid node type
    
    Parameters
    ---
    type_module - `module`
        module that contains the Node classes for the type
    type_name - `str`
        name of the type, should match the TYPE in the GraphNode class
    re-register - `bool`
        boolean for whether or not it's ok to override if already registered. prints out warning if trying to re-register and this is false'''
    parsing_logger.debug(f"trying to register a node under <{type_name}>")
    validate_type(type_module, type_name)
    graph_node_ref = getattr(type_module, type_name+"GraphNode")
    
    if graph_node_ref.TYPE in ALLOWED_NODE_TYPES and not re_register:
        parsing_logger.warning(f"type <{graph_node_ref.TYPE}> already registered, and not allowed to re-register. skipping")
    else:
        ALLOWED_NODE_TYPES[graph_node_ref.TYPE] = type_module
        # if re-registering, probably a good idea to get rid of any potential stale data
        if re_register and graph_node_ref.TYPE in NODE_DEFINITION_CACHE:
            del NODE_DEFINITION_CACHE[graph_node_ref.TYPE]
        if re_register and graph_node_ref.TYPE in NODE_SCHEMA_CACHE:
            del NODE_SCHEMA_CACHE[graph_node_ref.TYPE]
        parsing_logger.debug(f"node type <{graph_node_ref.TYPE}> registerd, full list now is <{ALLOWED_NODE_TYPES}>")

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
        raise Exception(f"{version_string} is invalid version, must have three period separated whole numbers")
    second_dot=version_string.find(".",first_dot+1)
    if second_dot < 0:
        raise Exception(f"{version_string} is invalid version, must have three period separated whole numbers")
    try:
        version_tuple=(int(version_string[:first_dot]),int(version_string[first_dot+1:second_dot]), int(version_string[second_dot+1:]))
    except:
        raise Exception(f"{version_string} is invalid version, must have three period separated whole numbers")
    return version_tuple

def validate_type(type_module, type_name):
    '''validates node type is formatted correctly. module must have two classes named: [type]GraphNode and [type]Node where you replace [type] with
    actual name of the type. GraphNode must have VERSION, DEFINITION, SCHEMA, TYPE fields. best to extend from BaseType. Raises Exception 
    if type is not formatted correctly.
    
    Parameters
    ---
    type_module - `module`
        module that contains the Node classes for the type
    type_name - `str`
        name of the type, should match the TYPE in the GraphNode class
    '''
    if not hasattr(type_module, type_name+"GraphNode") or not inspect.isclass(getattr(type_module, type_name+"GraphNode")):
        raise Exception(f"cannot find a <{type_name}GraphNode> class in node type <{type_name}> module.")
    if not hasattr(type_module, type_name+"Node") or not inspect.isclass(getattr(type_module, type_name+"Node")):
        raise Exception(f"cannot find a <{type_name}Node> class in node type <{type_name}> module.")
    
    #TODO: check duck typing: all needed methods are there? lots of methods though
    
    graph_node = getattr(type_module, type_name+"GraphNode")
    if graph_node.TYPE != type_name:
        # this is an exception because GraphNode.TYPE will be used by yaml and code to know the type. Classes' names must have type in them
        # type_name is not saved, so if refilling schema caches later, it'll be harder to find classes from the GraphNode.TYPE
        raise Exception(f"passed in node type <{type_name}> is different from recorded type in GraphNode <{graph_node.TYPE}>. " +\
                        f"Needs to be the same so system can find node info reliably.")
    
    # parse version already throws exceptions if formatted badly so can use that to check. catching to make error message more relevant to here
    try:
        parse_version_string(graph_node.VERSION)
    except Exception as e:
        raise Exception(f"node type <{type_name}> does not have a valid version string {e}")
    

    parsed_def = yaml.safe_load(graph_node.DEFINITION)
    print("test",parsed_def)
    if not isinstance(parsed_def, dict) or "options" not in parsed_def:
        raise Exception(f"node type <{type_name}> cannot be used. definition must have options key")
    elif parsed_def["options"] is None:
        raise Exception(f"node type <{type_name}> options key data missing, if trying to have empty set please use \"options: []\"")
    for option in parsed_def["options"]:
        if "name" not in option:
            raise Exception(f"node type <{type_name}> cannot be used. An option in definition is missing a name")
    
    parsed_schema = yaml.safe_load(graph_node.SCHEMA)
    #TODO: maybe use some of JSONSchema validate schema stuff? not sure if exists and how yet
    if not isinstance(parsed_schema, dict):
        raise Exception(f"node type <{type_name}> cannot be used. badly formatted schema")
    
def load_type(node_type):
    '''loads an allowed node type's definition and schema into caches. These will be needed during parsing to know what data to use and format of it.
    Raises Exception if couldn't find type or node type badly defined
    
    Parameters
    node_type - `str`
        name of the type to load'''
    parsing_logger.debug(f"loading type <{node_type}>")
    try:
        graph_node = getattr(ALLOWED_NODE_TYPES[node_type], node_type+"GraphNode")
        NODE_DEFINITION_CACHE[node_type] = yaml.safe_load(graph_node.DEFINITION)
        # dev creating node types should make sure schema for variables introduced by that type is valid
        NODE_SCHEMA_CACHE[node_type] = yaml.safe_load(graph_node.SCHEMA)
    except KeyError as e:
        raise Exception(f"tried to load information about node type named <{node_type}> but couldn't. type isn't registered")
    except Exception as e:
        raise Exception(f"tried to load information about node type named <{node_type}> but couldn't. details: {e}")
    
def empty_cache():
    '''empties cache for different node types' definitions and schemas'''
    NODE_DEFINITION_CACHE.clear()
    NODE_SCHEMA_CACHE.clear()

#~~~~~~~~~ SOME FURTHER SETUP ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# always needed, and might as well use the registration functions that handle checks already
register_node_type(BaseType, "Base")
load_type("Base")
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_name(name):
    #TODO: future QoL WIP, potentially for names with . in them
    pass

def parse_files(*file_names:str, existing_nodes:dict = None):
    '''same idea as `parse_file` parses all the passed in files for nodes and appends them onto existing nodes. Can handle multiple yaml documents
    in files. raising error if already there or graph node definition badly formatted
    
    Parameters
    ---
    file_names - any number of strings
        variable number of comma separated yaml files names to look for nodes in
    existing_nodes - `dict`
        dictionary of node id to GraphNode object, parsing treats it as previously parsed nodes you don't want overwritten by newly read nodes
        
    Return
    ---
    dict
        same format as passed in existing nodes. list of existing nodes with ones just parsed from file added'''
    existing_nodes = existing_nodes if existing_nodes is not None else {}
    for file_name in file_names:
        parse_file(file_name, existing_nodes)
    return existing_nodes

def parse_file(file_name, existing_nodes:dict=None):
    '''parses a file for nodes and appends them onto existing nodes. Can handle multiple yaml documents
    in files. Raises error if already there or graph node definition badly formatted
    
    Parameters
    ---
    file_name - `string`
        yaml files name to look for nodes in
    existing_nodes - `dict`
        dictionary of node id to GraphNode object, parsing treats it as previously parsed nodes you don't want overwritten by newly read nodes
    
    Return
    ---
    dict
        same format as passed in existing nodes. list of existing nodes with ones just parsed from file added'''
    existing_nodes = existing_nodes if existing_nodes is not None else {}
    num_added = 0
    with open(file_name) as file:
        parsing_logger.debug(f"loading file <{file_name}>, with existing nodes <{existing_nodes}>")
        doc_dict = yaml.safe_load_all(file)
        for doc_ind, yaml_doc in enumerate(doc_dict):
            parsing_logger.debug(f"parsing document indexed <{doc_ind}> from file <{file_name}>")
            if yaml_doc is None or "nodes" not in yaml_doc or yaml_doc["nodes"] is None or len(yaml_doc["nodes"]) == 0:
                parsing_logger.info(f"file {file_name} document indexed {doc_ind} does not have list of nodes, moving to next YAML document")
                continue
            
            for node_ind, yaml_node in enumerate(yaml_doc["nodes"]):
                node = parse_node(yaml_node, location_printout=f"file <{file_name}> doc <{doc_ind}> node <{node_ind}>")
                if node.id in existing_nodes:
                    # technically could ignore second, but better to tell whoever wrote it so any differences don't cause confusion of why misbehaving
                    raise Exception(f"Exception at file {file_name} doc {doc_ind} node {node_ind}, node <{node.id}> is already loaded, can't accept the second definition")
                num_added += 1
                existing_nodes[node.id] = node
                parsing_logger.debug(f"existing nodes are now <{existing_nodes}>")

    parsing_logger.info(f"finished loading file <{file_name}>, found <{num_added}> nodes from file")
    return existing_nodes

def parse_node(yaml_node, location_printout=""):
    '''function that takes yaml for one node and validates and creates a GraphNode object of the type specified in yaml.
    raises errors for anything wrong in node definition
    
    Parameters
    ---
    yaml_node - `dict`
        loaded yaml object that holds the node's settings
    location_printout - `str`
        extra information to print out in logging or exceptions to help with finding where in the yaml file the error came from
        
    Return
    ---
    GraphNode
        graph node class that represents the type specified in yaml'''
    parsing_logger.debug(f"parsing node.{' located in '+location_printout if len(location_printout) > 0 else ''}")
    node_type = validate_yaml_node(yaml_node, location_printout)
    
    # get all options that need to be filled in GraphNode, design is types can extend each other to add more fields
    # NOTE: this part will need to be changed if allowing extending from nodes other than base
    all_options = [*NODE_DEFINITION_CACHE["Base"]["options"]]
    if node_type != "Base":
        # techinally allows for child class to override definitions by loading it later.
        all_options.extend(NODE_DEFINITION_CACHE[node_type]["options"])

    parsing_logger.debug(f"options to look for in node are (note there might be repeats becuase option appears in both child and parent nodes): <{all_options}>")
    graph_node_model = {}
    for option in all_options:
        # used to check if option is required but not in yaml, but handled by schema check now
        if option["name"] not in yaml_node:
            if "default" not in option:
                # most cases, this should be listed as required in schema
                raise Exception(f"node {'located in '+location_printout+' ' if len(location_printout) > 0 else ''}found optional value '{option['name']}' missing fron yaml and no default value specified")
            graph_node_model[option["name"]] = copy.deepcopy(option["default"])
        else:
            graph_node_model[option["name"]] = copy.deepcopy(yaml_node[option["name"]])
    # in case there's extra steps from node to verify or format data passed in, moved into constructor

    graph_node=getattr(ALLOWED_NODE_TYPES[node_type],node_type+"GraphNode")(graph_node_model)
    parsing_logger.debug(f"parsed node is <{graph_node.id}>")
    return graph_node

def validate_yaml_node(yaml_node, location_printout=""):
    '''validates yaml definition of node. checks type is allowed, version is close enough to Class definition's version, and validates using schema.
    raises errors if node type is not allowed, versions are too far, bad node type definitions, or any other bad formatting in yaml

    Parameters
    ---
    yaml_node - `dict`
        loaded yaml object that holds the node's settings
    location_printout - `str`
        extra information to print out in logging or exceptions to help with finding where in the yaml file the error came from
        
    Return
    ---
    string
        node type pf just validated node'''
    node_type = "Base" #default assumed type, the most basic node
    if "Base" not in ALLOWED_NODE_TYPES:
        parsing_logger.critical(f"something is very badly weirdly wrong. trying to validate but Base Type was removed"+\
                                "from allowed node types. re-registering but check execution to make sure this doesn't happen")
        register_node_type(BaseType, "Base")
    if "type" in yaml_node:
        if yaml_node["type"] not in ALLOWED_NODE_TYPES.keys():
            raise Exception(f"{'located in '+location_printout+', ' if len(location_printout) > 0 else ''}<{yaml_node['type']}> is unknown type")
        node_type = yaml_node["type"]
    
    # version label is grabbed, semi-checked since don't know what else is needed for it
    node_version = None
    if "version" in yaml_node:
        node_version = yaml_node["version"]
    elif "v" in yaml_node:
        node_version = yaml_node["v"]
    
    if not node_version:
        parsing_logger.warning(f"yaml node {'located in '+location_printout+' ' if len(location_printout) > 0 else ''}found without version, "+\
                                     f"assuming most recent version of {getattr(ALLOWED_NODE_TYPES[node_type],node_type+'GraphNode').VERSION}")
        node_version = getattr(ALLOWED_NODE_TYPES[node_type],node_type+"GraphNode").VERSION

    actual_version = parse_version_string(node_version)
    target_version = parse_version_string(getattr(ALLOWED_NODE_TYPES[node_type],node_type+"GraphNode").VERSION)
    if actual_version[0] != target_version[0] or actual_version[1] != target_version[1]:
        raise Exception(f"yaml node {'located in '+location_printout+' ' if len(location_printout) > 0 else ''}has version of <{node_version}> is "+ \
                        f"too different from version of node definion loaded ({getattr(ALLOWED_NODE_TYPES[node_type],node_type+'GraphNode').VERSION}), "+ \
                        f"please update yaml definition or load matching version")
    #TODO: are there more checking version mismatches?
    # make sure type definition already parsed as well
    if node_type not in NODE_DEFINITION_CACHE:
        load_type(node_type)

    try:
        if node_type != "Base":
            #TODO: probably need something to merge schemas, this will treat the two as independent, and can't use child classes to override base schema
            #TODO: also probably need to make recursive to handle extend chains
            validate(yaml_node, {"allOf": [NODE_SCHEMA_CACHE[node_type], NODE_SCHEMA_CACHE["Base"]]})
        else:
            validate(yaml_node, NODE_SCHEMA_CACHE["Base"])
    except ValidationError as ve:
        # schema validation failed. want to catch and print the error information in a format that is easier to debug than default.
        # error printout on terminal still prints out the original version of the error before the custom one though
        path_elements = [str(x) for x in ve.absolute_path]
        path = "node"
        if len(path_elements) > 0:
            path+="."+'.'.join(path_elements)
        except_message = f"Exception {'located in '+location_printout+', ' if len(location_printout) > 0 else ''}"\
                        "yaml definition provided does not fit expected format within '"\
                        f"{path}' error message: {ve.message}"
        raise Exception(except_message)
    
    return node_type