import v2.DialogHandling.DialogObjects as DialogObjects
import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing
import v2.DialogHandling.BuiltinNodeDefinitions.BaseNode as BaseNodeDefinitions
'''Template for new node definitions. Do not instantiate these. Two classes are needed as of alpha2.0. First class called 'Layout' stores
    the base information about the node. The other class called 'Node' is for when there is an instance of this layout active and waiting for responses.
    Node objects are created for tracking events happening, layout objects are for tracking generally how all active Node objects of that type should 
    behave. Node objects represent one instance each and only of one (the corresponding layout) type'''


class TemplateLayout(BaseNodeDefinitions.BaseGraphNode):
    type = "FILL IN WITH YOUR TYPE, UNIQUE KEY AMONG ALL NODES USED"
    def __init__(self, args):
        '''call from parsing after formatting things correctly. The exact format and number for fields specific to this node is up to designer.
        Just make sure active node is accessing the right fields when the data is needed.
        Some fields are common across all nodes. `id` is expected to be hashable key for each layout node object loaded into the same handler. `type`
        is usually a string to represent type. `next_node` can be in node or sub fields, it must be the id of the next node.'''
        super().__init__(args)
        # insert grabbing this node specific fields here
        pass

    async def do_node(self, handler, save_data, interaction_msg_or_context, event_object_class, msg_options={}):
        '''this method is called when a handler says its time to create an active node of this layout, and is for node to do whatever 
        actions it needs to create an active node instance such as sending a discord message to wait for responses on
        * `handler` - the Dialog handler object calling this method.
        * `save_data` - the data from user making progress through previous nodes or None. expected to attach to active node object
        * `interaction_msg_or_context` - the object that represents context for node activation. could be interaction, message, or context class. 
            useful as a starting point for which channel to send a message in or just responding to interaction
        * `context_object_type` - string representing the class of the previous object. can use this or recalculate it yourself
        * `msg_options` - any options passed in from elsewhere to use when sending the discord message
        
        Return
        ---
        Must return a Node instance.
        '''
        pass

    @classmethod
    def parse_node(cls, yaml_node):
        '''method for parsing fields defining an instance of this type of layout node. Each layout's parse is responsible for parsing and 
        enforcing fields specific to this layout. Parsing of fields for all layouts is handled by parse_node. Common fields allowed in all nodes
        might have parsing methods in DialogNodeParsing file if they are complex. Recommend using those methods, especially for next_node
        
        Parameter
        ---
        `yaml_node` - dictionary storing fields read from yaml definition

        Return
        ---
        tuple
            msut return tuple where first element is the layout node object for the definition that was passed in, second is list of layout 
            nodes whose definitions were found nested inside. Recommend passing each nested definition to DialogNodeParsing.parse_node to take
            care of. Be sure to go through and check for duplicate node definitions
        '''
        pass

class TemplateNode(BaseNodeDefinitions.BaseNode):
    def __init__(self, layout_node, save_data=None, channel_message=None):
        ''''''
        super().__init__(layout_node, save_data, channel_message)
        # insert setting up this node specific fields here

    async def filter_event(self, event):
        '''try to keep this method fast as it can be called while trying to respond to a discord Interaction. Called by handler when event has happend
        on this node and is last stage filtering for if the event is actually something that should be allowed to be processed. Good for checking if 
        user who interacted is the one we want etc.
        `event` - can be interaction, message, etc event that this node is able (decided by designer) to process
        
        Return
        ---
        bool - if event should be allowed to proceed to being processed and considered "has happened on node"'''
        pass

    async def process_event(self, handler, event):
        ''''''
        pass

    async def update_save(self, interaction, data_loc):
        pass

    async def get_chaining_info(self, interaction):
        pass

    async def post_chaining(self, chaining_status, next_node_layout):
        pass

    async def can_close(self):
        pass

    async def close(self, was_fulfilled):
        await super().close(was_fulfilled=was_fulfilled)