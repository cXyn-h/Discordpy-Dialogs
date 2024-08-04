import src.DialogNodes.BaseType as BaseType

def test_parsed_fields_copy():
    if "CLASS_FIELDS" in vars(BaseType.BaseGraphNode).keys():
        BaseType.BaseGraphNode.clear_caches()
    fields = BaseType.BaseGraphNode.get_node_fields()
    assert fields is not BaseType.BaseGraphNode.CLASS_FIELDS
    fields2 = BaseType.BaseGraphNode.get_node_fields()
    assert fields2 is not BaseType.BaseGraphNode.CLASS_FIELDS

def test_parsed_schema_copy():
    if "PARSED_SCHEMA" in vars(BaseType.BaseGraphNode).keys():
        BaseType.BaseGraphNode.clear_caches()
    schema = BaseType.BaseGraphNode.get_node_schema()
    assert schema is not BaseType.BaseGraphNode.PARSED_SCHEMA
    schema2 = BaseType.BaseGraphNode.get_node_schema()
    assert schema2 is not BaseType.BaseGraphNode.PARSED_SCHEMA