import copy
import yaml
import os
from jsonschema import Draft202012Validator

def parse_schema_or_loc(schema_or_path, folder_start=None):
    '''takes loaded dict or string path pointing to yaml file that has schema.
        if folder_start is none, assumes was passed a schema. otherwise assumes a path
        schema information mmust must be single yaml document and define a single schema. Path must be relative from folder_start.

        Returns
        ---
        loaded schema. will be file contents if path, or the thing passed in otherwise
        '''
    if folder_start is None:
        schema = schema_or_path
    else:
        schema_path = os.path.abspath(os.path.join(folder_start, schema_or_path))
        with open(schema_path) as file:
            schema = yaml.safe_load(file)

    #TODO: adjusting for different drafts
    Draft202012Validator.check_schema(schema)
    return schema

def get_validator_class():
    #TODO: adjusting for different drafts
    return Draft202012Validator
    
