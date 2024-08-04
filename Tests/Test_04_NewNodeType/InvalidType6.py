import src.DialogNodes.BaseType as BaseType

# INVALID because root of definition wrong form

class TestGraphNode(BaseType.BaseGraphNode):
    TYPE = "Test"
    ADDED_FIELDS='''
WRONGdefinition'''
    SCHEMA = '''
type: object
properties:
    graph_start:
        type: object
        patternProperties:
            ".+":
                anyOf:
                    - type: "null"
                    - type: "object"
                      properties:
                        filters:
                            type: array
                            items:
                                type: ["string", "object"]
                        actions:
                            type: array
                            items:
                                type: ["string", "object"]
                      unevaluatedProperties: false
        unevaluatedProperties: false'''
    # VERSION="1.0.0"
    pass

class TestNode(BaseType.BaseNode):
    pass
