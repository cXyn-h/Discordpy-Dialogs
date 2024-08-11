import src.DialogNodeParsing as NodeParser
import ValidTestType as VT
import ValidTestType2 as VT2
import ValidTestType3 as VT3
import pytest

def test_validate_mirrors_changes():
    '''test edge case of module fields changing, if validate will pick up the changes when it runs'''
    import InvalidType6 as ITT6 # root of definition wrong form
    old_parsed_fields = VT2.ValidTestGraphNode.get_node_fields()
    old_fields = VT2.ValidTestGraphNode.ADDED_FIELDS
    assert "CLASS_FIELDS" in vars(VT2.ValidTestGraphNode).keys()
    assert VT2.ValidTestGraphNode.CLASS_FIELDS is not None
    VT2.ValidTestGraphNode.ADDED_FIELDS = ITT6.TestGraphNode.ADDED_FIELDS
    assert old_parsed_fields == VT2.ValidTestGraphNode.CLASS_FIELDS[1]
    with pytest.raises(Exception):
        NodeParser.validate_type(VT2, "ValidTest")
    
    VT2.ValidTestGraphNode.ADDED_FIELDS = old_fields
    assert not "CLASS_FIELDS" in vars(VT2.ValidTestGraphNode).keys()
    NodeParser.validate_type(VT2, "ValidTest")
    assert old_parsed_fields == VT2.ValidTestGraphNode.CLASS_FIELDS[1]

def test_new_type_schemas():
    '''make sure schemas are merged as expected for new types'''
    VT_schema = VT.ValidTestGraphNode.get_node_schema()
    VT2_schema = VT2.ValidTestGraphNode.get_node_schema()
    VT3_schema = VT3.ValidTestGraphNode.get_node_schema()

    assert len(VT_schema["allOf"]) == 2
    assert len(VT2_schema["allOf"]) == 2
    assert len(VT3_schema["allOf"]) == 2