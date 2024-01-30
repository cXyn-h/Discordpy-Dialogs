import src.DialogNodes.BaseType as BaseType

# INVALID because option in definition badly formatted

class TestGraphNode(BaseType.BaseGraphNode):
    TYPE = "Test"
    FIELDS='''
options:
  - name: key1
    default: Null
  - name: key2
  - default: 0'''
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
