import src.DialogNodes.BaseType as BaseType

# INVALID because definition Null options

class TestGraphNode(BaseType.BaseGraphNode):
    TYPE = "Test"
    FIELDS='''
options:'''
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
