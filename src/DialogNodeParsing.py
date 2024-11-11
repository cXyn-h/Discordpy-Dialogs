import yaml
import copy
import inspect
import logging

# known node type to parse to
import src.DialogNodes.BaseType as BaseType
# pretty log messages and other tools
import src.utils.LoggingHelper as logHelper

# for validing yaml has right format. 
# why *JSON*schema? because it validates based on already read in dictionaries. Once yaml is read in there's no difference
from jsonschema import validate, ValidationError
import types
#TODO: future: autoimport nodes from folder?

parsing_logger = logging.getLogger('Dialog Parser')
logHelper.use_default_setup(parsing_logger)
parsing_logger.setLevel(logging.INFO)

ALLOWED_NODE_TYPES = {}
'''The global cache of what types of nodes the parser can handle. dinctionary of node type name to node type module.
    that single module should contain both GraphNode and active Node of the type'''
#~~~~~~~~~ FURTHER SETUP OF THESE ARE DONE AFTER DEFINING FUNCTIONS FOR HANDLING AND REGESTERING ~~~~~~~~~

def find_node_classes(type_module:types.ModuleType):
    '''
    finds node types that have both classes defined within a module, not necessarily fully valid node type definition. 
    note that while technically you can have more than one Node type's classes in a file,
    its not recommended for organization sake. Module must have both GraphNode and active Node classes of a type defined to support the type.

    Parameters
    ---
    type_module - `module`
        module that contains the GraphNode and Node classes for the type
    
    Return
    ---
    a list of type names that have both classes defined within module. Those still may not be valid nodes'''
    found_graph_node_types = []
    found_node_types = []
    for name, obj in inspect.getmembers(type_module):
        if inspect.isclass(obj):
            if name.endswith("GraphNode"):
                found_graph_node_types.append(name[:name.find("GraphNode")])
            elif name.endswith("Node"):
                found_node_types.append(name[:name.find("Node")])

    supported_types = []
    # type considered supported if both GraphNode and active Node classes are present
    # looping through one list is enough because looking for things in both. everything that could pass needs to be in
    #   list that we randomly pick to be the one to loop through
    for type in found_graph_node_types:
        if type in found_node_types:
            supported_types.append(type)
    return supported_types

def register_node_type(type_module, type_name:str, re_register=False, allowed_types:"dict[str, types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''validates and if passes validation registers the given node type so the parser can use it. Raises Exceptions for invalid node type

    Parameters
    ---
    type_module - `module`
        module that contains the GraphNode and Node classes for the type
    type_name - `str`
        name of the type, should match the TYPE field in the GraphNode class and the name of the class
    re-register - `bool`
        boolean for whether or not it's ok to override if already registered. prints out warning if trying to re-register and this is false
    allowed_types - `dict[str, module]`
        dictonary of types that are already registered and allowed to use for parsing. uses global storage dictionary as default, otherwise can override
        with local registries

    Raises
    ---
    Exception if type fails validation
        
    Returns
    ---
    `bool` - wether or not type was registered or re-registered'''

    parsing_logger.debug(f"trying to register a node under <{type_name}>")
    # if not valid, it will error out and won't finish registering
    validate_type(type_module, type_name)
    graph_node_ref:BaseType.BaseGraphNode = getattr(type_module, type_name+"GraphNode")

    if graph_node_ref.TYPE in allowed_types and not re_register:
        parsing_logger.warning(f"type <{graph_node_ref.TYPE}> already registered, and not allowed to re-register. skipping")
        return False
    else:
        # if re-registering, likely should clear out caches. validate already does that so no need here
        allowed_types[graph_node_ref.TYPE] = type_module
        parsing_logger.debug(f"node type <{graph_node_ref.TYPE}> registerd, full list now is <{allowed_types}>")
        return True

def validate_type(type_module:types.ModuleType, type_name:str):
    '''validates node type is formatted correctly. module must have two classes named: [type]GraphNode and [type]Node where you replace [type] with
    actual name of the type. GraphNode must have TYPE field, and be able to fetch schema, fields and have a compatible version. 
    best to extend from BaseType. Raises Exception if type is not formatted correctly.

    Parameters
    ---
    type_module - `module`
        module that contains the Node classes for the type
    type_name - `str`
        name of the type, should match the TYPE in the GraphNode class

    Raises
    ---
    Exception if badly formatted type - missing classes, TYPE field mismatch, failed to fetch node fields
    '''
    if not hasattr(type_module, type_name+"GraphNode") or not inspect.isclass(getattr(type_module, type_name+"GraphNode")):
        raise Exception(f"cannot find a <{type_name}GraphNode> class in node type <{type_name}> module.")
    if not hasattr(type_module, type_name+"Node") or not inspect.isclass(getattr(type_module, type_name+"Node")):
        raise Exception(f"cannot find a <{type_name}Node> class in node type <{type_name}> module.")

    graph_node:BaseType.BaseGraphNode = getattr(type_module, type_name+"GraphNode")
    graph_node.clear_caches()
    if graph_node.TYPE != type_name:
        # this is an exception because GraphNode.TYPE will be used by yaml and code to know the type. Classes' names must have type in them
        # type_name is not saved, so if refilling schema caches later, it'll be harder to find classes from the GraphNode.TYPE
        raise Exception(f"passed in node type <{type_name}> is different from recorded type in GraphNode <{graph_node.TYPE}>. " + \
                        f"Needs to be the same so system can find node info reliably.")

    # UPDATE: version string format now entirely decided by node type, there's no enforcement from system
    # but kinda hacky way to do early check that the version in the class is correct by checking if compatible with itself
    is_compatible, warnings, = graph_node.check_version_compatibility(graph_node.get_version())
    if not is_compatible:
        raise Exception(f"node type <{type_name}> seems to have a broken version that does not work, or is not compatible with itself." + 
                        f" errors during check: {warnings}" if warnings else "")

    # making sure fields for this class can be retrieved
    # the method will raise exception if formatted incorectly, so just call early and let exception happen
    graph_node.get_node_fields()

    # let the node error out if it can't get a good version of a schema for itself
    graph_node.get_node_schema()
    #TODO: maybe use some of JSONSchema meta schema stuff to validate schema is usable by system? not sure how yet

def empty_cache(allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''empties cache for different node types' definitions and schemas. Nodes may store some cached data as well so clears node caches of the node types
    passed in as well'''
    for node_type, node_module in allowed_types.items():
        graph_node:BaseType.BaseGraphNode = getattr(node_module, node_type+"GraphNode")
        graph_node.clear_caches()

#~~~~~~~~~ SOME FURTHER SETUP ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Base is always needed, and might as well use the registration functions that handle checks already
register_node_type(BaseType, "Base", allowed_types=ALLOWED_NODE_TYPES)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_name(name):
    #TODO: future QoL WIP, potentially for names with . in them
    pass

def parse_files(*file_names:str, existing_nodes:dict = None, allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''same idea as `parse_file` parses all the passed in files for nodes and appends them onto existing nodes. Can handle multiple yaml documents
    in files. Raises error if GraphNode already found or GraphNode definition badly formatted

    Parameters
    ---
    file_names - any number of strings
        variable number of comma separated yaml file names to look for nodes within
    existing_nodes - `Optional[dict]`
        dictionary of node id to GraphNode object, parsing treats this as previously parsed nodes you don't want overwritten by newly read nodes
    allowed_types - `dict[str, module]`
        dictonary of types that are already registered and allowed to use for parsing. uses global storage dictionary as default, otherwise can override
        with local registries

    Return
    ---
    dict
        same format as passed in existing nodes: node id to GraphNode object. list of existing nodes with ones just parsed from file added'''
    # don't want truthy comparison so user can pass in a dict object they want filled
    existing_nodes = existing_nodes if existing_nodes is not None else {}
    for file_name in file_names:
        parse_file(file_name, existing_nodes, allowed_types=allowed_types)
    return existing_nodes

def parse_file(file_name, existing_nodes:dict=None, allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''parses a file for nodes and appends them onto existing nodes. Can handle multiple yaml documents
    in files. Raises error if already there or graph node definition badly formatted

    Parameters
    ---
    file_name - `string`
        yaml file's name to look for nodes within
    existing_nodes - `Optional[dict]`
        dictionary of node id to GraphNode object, parsing treats this as previously parsed nodes you don't want overwritten by newly read nodes
    allowed_types - `dict[str, module]`
        dictonary of types that are already registered and allowed to use for parsing. uses global storage dictionary as default, otherwise can override
        with local registries

    Return
    ---
    dict
        same format as passed in existing nodes: node id to GraphNode object. list of existing nodes with ones just parsed from file added'''
    # don't want truthy comparison so user can pass in a dict object they want filled
    existing_nodes = existing_nodes if existing_nodes is not None else {}
    with open(file_name) as file:
        doc_dict = yaml.safe_load_all(file)
        parse_contents(doc_dict, file_name, existing_nodes=existing_nodes, allowed_types=allowed_types)
    parsing_logger.info(f"finished loading file <{file_name}>")
    return existing_nodes

def parse_contents(doc_dict, file_location = "", existing_nodes:dict=None, allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    existing_nodes = existing_nodes if existing_nodes is not None else {}
    file_location = 'file: ' + file_location if file_location else 'string'
    parsing_logger.debug(f"loading content from <{file_location}>, with existing nodes <{existing_nodes}>")
    for doc_ind, yaml_doc in enumerate(doc_dict):
        parsing_logger.debug(f"parsing document indexed <{doc_ind}> from <{file_location}>")
        if yaml_doc is None or "nodes" not in yaml_doc or yaml_doc["nodes"] is None or len(yaml_doc["nodes"]) == 0:
            parsing_logger.info(f"parsed from {file_location} document indexed {doc_ind} does not have list of nodes, moving to next YAML document")
            continue

        for node_ind, yaml_node in enumerate(yaml_doc["nodes"]):
            node = parse_node(yaml_node, file_location=f"location <{file_location}> doc <{doc_ind}> node <{node_ind}>", allowed_types=allowed_types)
            if node.id in existing_nodes:
                # technically could ignore second, but better to tell whoever wrote it so any differences don't cause confusion of why misbehaving
                raise Exception(f"Exception in {file_location} doc {doc_ind} node {node_ind}, node <{node.id}> is already loaded, can't accept the second definition")
            parsing_logger.debug(f"added node <{node.id}>")
            existing_nodes[node.id] = node
    return existing_nodes

def parse_node(yaml_node, file_location="", allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''function that takes yaml for one node and validates and creates a GraphNode object of the type specified in yaml.
    raises errors for anything wrong in node definition

    Parameters
    ---
    yaml_node - `dict`
        loaded yaml object that holds the node's settings
    file_location - `str`
        extra information to print out in logging or exceptions to help with finding where in the yaml file the error came from

    Return
    ---
    GraphNode
        graph node class that represents the type specified in yaml'''
    parsing_logger.debug(f"parsing node.{' located in '+file_location if len(file_location) > 0 else ''}")
    node_type = validate_yaml_node(yaml_node, file_location, allowed_types=allowed_types)

    try:
        node_class = getattr(allowed_types[node_type], node_type+"GraphNode")
        graph_node:BaseType.BaseGraphNode = node_class(yaml_node)
    except Exception as e:
        raise Exception(f"node {'located in '+file_location+' ' if len(file_location) > 0 else ''} errored: {e}")
    parsing_logger.debug(f"parsed node is <{graph_node.id}>")
    return graph_node

def validate_yaml_node(yaml_node, file_location="", allowed_types:"dict[str,types.ModuleType]"=ALLOWED_NODE_TYPES):
    '''validates parsed yaml correctly defines a node. checks type is allowed, version is close enough to Class definition's version, and validates using schema.
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
        node type of just validated node'''

    node_type = "Base" # default assumed type, the most basic node
    if "Base" not in allowed_types:
        parsing_logger.critical(f"something is very badly weirdly wrong. trying to validate but Base Type was removed"+\
                                "from allowed node types list. re-registering but check execution to make sure this doesn't happen")
        register_node_type(BaseType, "Base", allowed_types=allowed_types)
    if "type" in yaml_node:
        if yaml_node["type"] not in allowed_types.keys():
            raise Exception(f"found node {'located in '+file_location+', ' if len(file_location) > 0 else ''}<{yaml_node['type']}> is unknown type. says {yaml_node['type']} but type is not registered")
        node_type = yaml_node["type"]

    graph_node:BaseType.BaseGraphNode = getattr(allowed_types[node_type], node_type+"GraphNode")

    # version label is grabbed and checked. each node type handles versions separately
    # as of node v3.8.0 "v" shorthand not supported anymore
    node_version = None
    if "version" in yaml_node and "v" in yaml_node:
        raise Exception(f"yaml node {'located in '+file_location+' ' if len(file_location) > 0 else ''}has two keys specifying version, use only one")
    elif "version" in yaml_node:
        node_version = yaml_node["version"]
    elif "v" in yaml_node:
        parsing_logger.warning(f"v field deprecated, please use version instead")
        node_version = yaml_node["v"]

    if not node_version:
        # assume is latest version and try that. error later.
        # if version is required, that is on the node to specify
        parsing_logger.debug(f"yaml node {'located in '+file_location+' ' if len(file_location) > 0 else ''}found without version")
        node_version = graph_node.VERSION

    # version is all up to node itself so let node decide if read in version works with loaded node
    is_compatible, warnings = graph_node.check_version_compatibility(node_version)

    if is_compatible:
        if warnings:
            parsing_logger.warning(f"yaml node {'located in '+file_location+' ' if len(file_location) > 0 else ''}has some version warnings: {warnings}")
    else:
        raise Exception(f"yaml node {'located in '+file_location+' ' if len(file_location) > 0 else ''}has version of <{node_version}> that is not compatible." +
                        f" errors from version check: {warnings}" if warnings else "")

    try:
        validate(yaml_node, graph_node.get_node_schema())
    except ValidationError as ve:
        # schema validation failed. want to catch and print the error information in a format that is easier to debug than default.
        # error printout on terminal still prints out the original version of the error before the custom one though
        path_elements = [str(x) for x in ve.absolute_path]
        path = "node"
        if len(path_elements) > 0:
            path+="."+'.'.join(path_elements)
        except_message = f"Exception {'located in '+file_location+', ' if len(file_location) > 0 else ''}"\
                        "yaml definition provided does not fit expected format within '"\
                        f"{path}' error message: {ve.message}"
        raise Exception(except_message)

    return node_type