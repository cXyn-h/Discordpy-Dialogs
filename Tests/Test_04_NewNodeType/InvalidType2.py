import src.DialogNodes.BaseType as BaseType

# INVALID because GraphNode is not a class

TestGraphNode = {
    "TYPE": "Test",
    "ADDED_FIELDS":'''
options: []''',
    "SCHEMA": '''
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
}

class TestNode(BaseType.BaseNode):
    pass
