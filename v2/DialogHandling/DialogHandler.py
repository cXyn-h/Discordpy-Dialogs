import discord
from discord import ui, InteractionType, Interaction

import v2.DialogHandling.DialogNodeParsing as DialogNodeParsing

import yaml
import inspect
import logging
import sys
import asyncio
from datetime import datetime, timedelta

# this module is only used for testing. Can be removed once cleaning seems set up correctly
import random

dialog_logger = logging.getLogger('Dialog Handler')
# dialog_logging_handler = logging.StreamHandler(sys.stderr)
# dialog_logging_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
# dialog_logging_handler.setFormatter(dialog_logging_format)
# dialog_logger.addHandler(dialog_logging_handler)
dialog_logger.setLevel(logging.DEBUG)
# WIP alpha version, will have tons of logging printout and unfinished areas.

#TODO: future: variable content of message: grab at run not from file
#TODO: soon: implement save and load stored data about what's in progress
#       at least having on_interaction helps with hanging buttons on previous messages that were sent before restart,
#       but this would ensure any advanced filters on those would be saved through restart
#TODO: future: handle interaction checks in with active listeners and if interacted with node now needs to be deactivated, but
#       maybe custom limits like max number of reactors
#TODO: soon: Figure out what sorts of data get passed into callbacks
#       currently: dialog callbacks won't have progress or interaction ones
#       callbacks from interactions hve interaction, and progress if data has been added
#TODO: future: switching where next message will be sent
#TODO: soon: apparently created modals don't get garbage collected once they're submitted, it only seems to happen once the program ends
#TODO: future: custom defined nodes? partially there with a Base Node and regestering node types. needs fleshing out and documentation
#TODO: immediate: program-makes-a-choice-instead-of-waiting-for-user node
#TODO: soon: wait-for-any-message-based-on-filters-doesn't-need-to-be-reply node
#TODO: soon: using next step flag to indicate when one stage is completed might help? think it has to be on each option, but would it cause issues with now allowing multiple nodes in a step?
#TODO: soon: chaining, dealing with error of having node after flow progress is saved, and what happens when you re-enter that node with flow progress still active
#TODO: immediate: double checking user and node references used everywhere to verify events is correct. assumes that only one user per node. espcially the areas where
#       grabbing user from save vs one that generated event
#TODO: unknown: versioning yaml files
#TODO: unknown: do saved data entries need timeouts too? so they can get cleaned. currently getting cleaned when last node in chain gets closed
#TODO: soon: does close node need/should clean up save data?
#TODO: future: standardize events that come in
#TODO: future: custom event inputs to handler?
#TODO: soonish: full shakedown testing with a few people clicking buttons
#TODO: standardize node yaml variables?

class DialogHandler():
    supported_event_types = ["modal_submit", "reply", "interaction", "automatic"]
    '''the types of events that this handler supports, aka those that this handler will notify nodes when they happen. note that each 
    one may have different formats for keys to identify different active nodes for that event type'''
    # flag for development of cleaning task. should always be false at this point
    testing_cleaning_mode = False
    # passing in dialogs and callbacks if you want them shared between instances. not tested yet
    def __init__(self, nodes = {}, callbacks = {}, clean_freq_secs = 3) -> None:
        self.nodes = nodes
        self.callbacks = callbacks
        #TODO: soon: these probably need something that enforces certain structure to anything put inside
        #TODO: future: trackers need a once over to make sure things are cleaned up properly during timeouts, errors, dropped messages, bot crashes, regular stuff etc.
        self.flow_progress = {}
        self.active_nodes = []
        self.waiting_categories = {category:{} if category != "automatic" else [] for category in self.supported_event_types}
        self.cleaning_task = None
        self.clean_freq_secs = clean_freq_secs
        # some default available items
        self.register_dialog_callback(self.clean_clickables)
        self.register_dialog_callback(submit_results)
        # this dialog might not be used in future
        self.nodes["default_completed"] = DialogNodeParsing.parse_node({"id":"default_completed", "prompt":"completed"})

    '''################################################################################################
    #
    #                                   SETUP FUNCTIONS SECTION
    #
    ################################################################################################'''

    def load_file(self, file_name):
        '''load a yaml file with one or more yaml documents defining nodes into python objects. Those definitions are stored in self'''
        with open(file_name) as file:
            doc_dict = yaml.safe_load_all(file)
            for yaml_doc in doc_dict:
                for yaml_node in yaml_doc:
                    node, nested_nodes = DialogNodeParsing.parse_node(yaml_node)
                    if node.id in self.nodes:
                        raise Exception("node \""+node.id+"\" has been redefined.")
                    self.nodes[node.id] = node
                    for nested_node in nested_nodes:
                        if nested_node.id in self.nodes:
                            raise Exception("node \""+nested_node.id+"\" has been redefined")
                        self.nodes[nested_node.id] = nested_node

        dialog_logger.info("finished loading files")
        dialog_logger.debug("nodes: %s", self.nodes)
    
    def final_validate():
        #TODO: future: function goes through all loaded dialog stuff to make sure it's valid. ie all items have required parems, 
        #       parems are right format, references point to regestered commands and dialogs, etc
        pass

    # this makes it eaiser, one spot to find all functions. and also good for security against bad configs
    def register_dialog_callback(self, func):
        '''adds passed in function to list of functions that are ok to be callback functions. Can be coroutines'''
        #TODO: future: how to make callbacks unmodifiable/inaccessible from outside?
        if func == self.register_dialog_callback:
            dialog_logger.warning("dialog handler tried registering the registration function, dropping for security reasions")
            return
        dialog_logger.debug("registered callback <%s>", func)
        self.callbacks[func.__name__] = func

    async def execute_command_callback(self, command_name, **kwargs):
        if not command_name:
            return
        # refining this is on todo list at top of file
        if command_name in self.callbacks:
            dialog_logger.info("doing command callback, command name <%s>. from node or option callback is unkown", command_name)
            if inspect.iscoroutinefunction(self.callbacks[command_name]):
                await self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)
            else:
                self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)
        else:
            dialog_logger.error("doing command callback but callback name <%s> not found", command_name)

    '''################################################################################################
    #
    #                           EXTRA DEBUGGING PRINTOUTS SECTION
    #
    ################################################################################################'''
   
    def print_detailed_saved_data(self):
        '''only for debugging purposes. prints out long form information about stored state'''
        try:
            indent = "   "
            if len(self.active_nodes) > 0:
                dialog_logger.debug(f"{indent}recorded nodes awaiting responses")
                for active_node in self.active_nodes:
                    dialog_logger.debug("%s%smemory address <%s>, node id <%s>, type <%s>, message id <%s>, save data address <%s>, save data <%s>",
                                        indent,indent,
                                        id(active_node), 
                                        active_node.layout_node.id,
                                        active_node.layout_node.type, 
                                        active_node.channel_message.id if active_node.channel_message else "N/A", 
                                        id(active_node.save_data) if active_node.save_data else "N/A", 
                                        active_node.save_data)
            else:
                dialog_logger.debug(f"{indent}no recorded nodes awaiting responses")
            
            if len(self.flow_progress) > 0:
                dialog_logger.debug(f"{indent}recorded save progress")
                for k,save_data in self.flow_progress.items():
                    reply_submit_info = ",".join(
                            ["{node id "+ node_id + "content "+ str(submission.content)+"}" for node_id,submission in save_data["reply_submits"].items()]
                            ) if "reply_submits" in save_data else ""
                    modal_submit_info = ",".join(
                            ["{node id "+ node_id + "content "+ str(submission)+"}" for node_id,submission in save_data["modal_submits"].items()]
                            ) if "modal_submits" in save_data else ""
                    dialog_logger.debug("%s%smemory address <%s> user id <%s> node id <%s> flag <%s> previous nodes <%s> all keys <%s> user data keys <%s>",
                                        indent,indent,
                                        id(self.flow_progress[k]),
                                        k[0],
                                        k[1],
                                        save_data["data"]['flag'] if 'flag' in save_data["data"] else 'N/A',
                                        save_data['prev_nodes'],save_data.keys(),
                                        save_data["data"].keys())

                    if "reply_submits" in save_data:
                        dialog_logger.debug(f"{indent}{indent}{indent}reply submit values")
                        dialog_logger.debug(f"{indent}{indent}{indent}{reply_submit_info}")
                    if "modal_submits" in save_data:
                        dialog_logger.debug(f"{indent}{indent}{indent}modal submit values")
                        dialog_logger.debug(f"{indent}{indent}{indent}{modal_submit_info}")
            else:
                dialog_logger.debug(f"{indent}no recorded flow progress")

            if len(self.waiting_categories) > 0:
                dialog_logger.debug(f"{indent}recorded waiting categories")
                for category, nodes in self.waiting_categories.items():
                    dialog_logger.debug(f"{indent}{indent}category: <{category}>, nodes <{str([id(nodes[x]) for x in nodes.keys()])}>")
            else:
                dialog_logger.debug(f"{indent}no recorded waiting categories")
        except Exception as e:
            dialog_logger.debug("detailed debug printout failed. probably should go fix that? details: <%s>", e)

    def print_compact_saved_data(self):
        '''only for debugging purposes. prints out a more compact form information about stored state'''
        try:
            open_dialog_info = ", ".join(["{id:"+id(x)+ " node:"+x.layout_node.id+" type:"+x.layout_node.type+"}" for x in self.active_nodes])
            dialog_logger.debug(f"active nodes awaiting responses {open_dialog_info}")
            dialog_logger.debug(f"open flow progress {self.flow_progress.keys()}")
        except Exception as e:
            dialog_logger.debug("compact debug printout failed. probably should go fix that? details: <%s>", e)


    '''################################################################################################
    #
    #                           SENDING NODES FUNCTION SECTION
    #
    ################################################################################################'''

    async def do_node_action(self, node_id, interaction_msg_or_context, save_data, event_object_class = None, msg_opts = {}):
        '''does the actions for a node being sent. events to start transitions to another node are handled in other areas. 
        
        Return
        ---
        `bool` - whether or not the action was successfully finished.'''
        dialog_logger.info("handler node action beginning node id <%s>", node_id)
        if not event_object_class:
            # just stores class name of object
            # having this passed around as well so this doesn't have to be recalculated
            event_object_class = type(interaction_msg_or_context).__name__
        if not node_id in self.nodes:
            dialog_logger.warning("trying to do node <%s> action but it is not laoded. ending attempt now and returning fail", node_id)
            return 0
        node_layout = self.nodes[node_id]
        try:
            # have the node take care of what it needs
            active_node = await node_layout.do_node(self, save_data, interaction_msg_or_context, event_object_class, msg_opts)
        except Exception as e:
            dialog_logger.warning("node <%s> do node failed <%s>. ending attempt and returning fail",node_layout.id, e)
            return 0

        activated_successfully = False
        for event_category in active_node.waits:
            if not event_category in self.waiting_categories:
                dialog_logger.warning("trying to do actions for <%s>, it is waiting for event this handler does not support: <%s>. ignoring.", node_id, event_category)
                continue
            activated_successfully = True
            # modals work on different keys, others can be message specific
            if event_category == "modal_submit":
                self.waiting_categories[event_category][(interaction_msg_or_context.user.id, interaction_msg_or_context.message.id)] = active_node
            elif event_category == "automatic":
                # self.waiting_categories[waiting].append(active_node) # no need to actually add to waiting if just gonna handle now
                self.handle_graph_event(active_node, interaction_msg_or_context, "automatic", event_object_class=event_object_class)
            else:
                self.waiting_categories[event_category][active_node.channel_message.id] = active_node
            dialog_logger.debug("node <%s> message id <%s> memroy address <%s> added to waiting for <%s> list", node_layout.id, active_node.channel_message.id if active_node.channel_message else "N/A", id(active_node), event_category)
        
        if activated_successfully:
            # node is waiting for events from handler
            self.active_nodes.append(active_node)
            dialog_logger.debug("dialog handler added node <%s> message id <%s> to active list, memory address <%s> save data attached <%s>, waiting for <%s>", 
                                node_layout.id, active_node.channel_message.id if active_node.channel_message else "N/A", id(active_node), active_node.save_data, active_node.waits)

            # do the command for the node, this is callback for when node has successfully been done
            try:
                if hasattr(node_layout, "command"):
                    await self.execute_command_callback(node_layout.command, open_dialog=active_node, progress=active_node.save_data)
            except Exception as e:
                dialog_logger.warning("node <%s> failed on callback <%s>, ignoring error and continuing",node_layout.id, e)
        else:
            # immediate closeing node since if it isn't waiting on anything it isn't active
            dialog_logger.info("immediate closing of node <%s> after doing it because it isn't actively waiting for anything", node_layout.id)
            await self.close_node(active_node)
        dialog_logger.info("end of node action node id <%s>", node_id)
        return 1

    '''################################################################################################
    #
    #                                   PROCESSING NODES SECTION
    #
    ################################################################################################'''
    
    async def find_interacted_node(self, interaction):
        ''' handle clicks on message components on messages or modal submits that are tracked as open dialogs. Does the first step of identifying 
        interaction type and which node is associated with interaction'''
        dialog_logger.info("dialog handler start handling interaction interaction id: <%s> message id: <%s> raw data in: <%s> interaction extras <%s>",
                           interaction.id, interaction.message.id, interaction.data, interaction.extras)

        # if statement because different types of interactions stored differently, different keys to find relavant active node
        if interaction.type == InteractionType.modal_submit:
            dialog_logger.info("handle interaction modal submit branch <%s>", InteractionType.modal_submit)

            if "modal_submit" not in self.waiting_categories or not (interaction.user.id, interaction.message.id) in self.waiting_categories["modal_submit"]:
                return
            interacted_node = self.waiting_categories["modal_submit"][(interaction.user.id, interaction.message.id)]
            await self.handle_graph_event(interacted_node, interaction, "modal", type(interaction).__name__)
        else:
            dialog_logger.info("handle interaction component interaction branch")
            if "interaction" not in self.waiting_categories or not interaction.message.id in self.waiting_categories["interaction"]:
                return
            interacted_node = self.waiting_categories["interaction"][interaction.message.id]
            await self.handle_graph_event(interacted_node, interaction, "interaction", type(interaction).__name__)

        dialog_logger.debug("handle interaction found interaction <%s> is for node <%s>", interaction.id, interacted_node.layout_node.id)

    async def handle_graph_event(self, active_node, event, event_type, event_object_class):
        '''method that processes changes event causes to node, doing the callback when event happens, and then passes it off to chain to the next node'''
        # interaction happened in valid location, now seeing if it is something that the interacted with node cares about processing
        if not await active_node.filter_event(event):
            dialog_logger.debug("handling component interaction, found active node memory address <%s> for node id <%s> and event does not pass filtering", 
                                id(active_node), active_node.layout_node.id)
            return
        dialog_logger.debug("found node interacted with memory address <%s> node id <%s> message id <%s>. save data attached <%s>, waiting for <%s>", 
                                id (active_node), active_node.layout_node.id, active_node.channel_message.id if active_node.channel_message else "N/A", active_node.save_data, active_node.waits)
        
        # valid event that we want to pay attention to. because of how active node might not have save data related to it but node layout definition 
        # may add data on interaction so now it does have data and how data is (currently) stored centrally in handler, need to query node and get it to
        # return any changes made so the handler can have a new entry in central store if it is added
        callback = await active_node.process_event(self, event)

        # if node has saved data attached to it, then that is going to be the object for all nodes that are in the same flow, so can just refer to it
        # and add the updates there. does mean have to be careful not to allow person interacting to backtrack though steps as previously visited nodes
        # that are farther along path can affect behavior on revisiting early nodes
        progress_after_interaction = None
        if active_node.save_data:
            # decided to let node manage updating its own data so that it can do any fancy stuff like updating a dictionary
            await active_node.update_save(event, active_node.save_data["data"])
            progress_after_interaction = active_node.save_data
        else:
            temp_new_loc = {}
            await active_node.update_save(event, temp_new_loc)
            if len(temp_new_loc) > 0:
                progress_after_interaction = {"curr_node": active_node.layout_node.id, "prev_nodes":set(), "data":temp_new_loc}
                if event_object_class == "Interaction":
                    dialog_logger.info("HEADS UP FOR DEBUGGING CHECK< NEW EVENT OBJECT CLASS CHECK IS WORKING")
                    progress_after_interaction.update({"user":event.user})
                else:
                    progress_after_interaction.update({"user":event.author})
            
        # handling callback stage, should always be together with process event since callback happens when valid event happens
        if callback:
            dialog_logger.info("doing callback <%s> for node <%s> at event", callback, active_node.layout_node.id)
            #TODO: updating callback when that is overhauled
            await self.execute_command_callback(callback, 
                    open_dialog=active_node, 
                    progress=progress_after_interaction, 
                    interaction=event)
        
        next_node_id, end = await active_node.get_chaining_info(event)
        await self.handle_chaining(active_node, next_node_id, end, progress_after_interaction, event_type, event)

    '''################################################################################################
    #
    #                           TRANSITIONING TO NODES METHODS SECTION
    #
    ################################################################################################'''

    async def start_at(self, node_id, interaction_msg_or_context, prev_save_progress = None):
        """method for starting conversation with bot. This is meant to be called from outside this module.
        
        Parameters
        ---
        `node_id` - str
            the id of the node to start at.
        `interaction_msg_or_context`
            the event that will provide context for this node. Nodes can use it to find channel to send to, the user who sent message/interaction
            or if its an interaction, respond to it.
        `prev_save_progress` - optional dict
            if there's save data that should be attached to node that is about to be created
        """
        event_object_class = type(interaction_msg_or_context).__name__

        goto_status = await self.goto_node(node_id, False, prev_save_progress, interaction_msg_or_context, event_object_class=event_object_class)
        if goto_status < 0:
            dialog_logger.warning("trying to start at node <%s> but failed when trying to do so", node_id)
            if event_object_class == "Interaction" and not interaction_msg_or_context.response.is_done():
                await interaction_msg_or_context.response.send_message(content="can't start dialog", ephemeral=True)
            else:
                await interaction_msg_or_context.channel.send(content="can't start dialog")

    async def goto_node(self, next_node_id, end_progress_transfer, save_data, interaction_msg_or_context, event_object_class=None):
        '''goes to the passed in next node by doing the node action and advancing any passed in save data. Exceptions from doing node are handled
        but all methods that call this are expected to handle logic for different cases of failure how it needs.
        
       Returns
       --- 
        uses return codes to report results. non negative considered success.
        * -3 next_node_id specified but failed to do next node's actions. any passed in save data is not changed or stored in 
        nodes or handler's central storage
        * -2 next_node_id specified but previous save progress found for next node, so blocking moving to it
        * -1 next_node_id specified but not properly loaded so couldn't find definition
        * 0 no next node specified
        * 1 next node was successfully handled and save data transferred
        * 2 next node was successfully handled and no save data or was not meant to be transferred'''
        rc = 0
        if not event_object_class:
            event_object_class = type(interaction_msg_or_context).__name__
        
        # because the way to access this is different, get a reference that is abstracted
        if event_object_class == "Interaction":
            interacting_user = interaction_msg_or_context.user
        else:
            interacting_user = interaction_msg_or_context.author
        
        if next_node_id and (next_node_id in self.nodes):
            # next node is found and valid, can do chaining
            if (interacting_user.id, next_node_id) in self.flow_progress:
                # data is centrally linked to in handler, and key structure means that reentering the same node might mean trying to use data from last
                # pass through node. Could get confusing and cause unexpected behavior so check to prevent that. alpha2.0 has active nodes link to flow
                # progress so might not be as needed to centrally store and check for repeats as each attempt can have separate data objects
                # if previous save data takes this path and moves to trying to clean up nodes part
                rc = -2
            else:
                # its also ok to go ahead and chain to next node 
                if not end_progress_transfer and save_data:
                    # save data should be transferred to next node. means updates to save data's status
                    dialog_logger.info("chaining is starting next node then moving data if there is any.")
                    next_node_success = await self.do_node_action(next_node_id, interaction_msg_or_context, save_data, event_object_class=event_object_class)
                    if next_node_success:
                        # next node was actually sucessfully sent. advance save data to point to next node
                        save_data["prev_nodes"].add(next_node_id)
                        save_data["curr_node"] = next_node_id
                        self.flow_progress[(interacting_user.id, next_node_id)] = save_data
                        dialog_logger.debug("found need to transfer data to next node. after transfer: save data <%s> all stored flow info <%s>", 
                                            save_data, ["("+str(k)+":"+str(id(v))+")" for k,v in self.flow_progress.items()])
                        rc = 1
                    else:
                        rc = -3
                else:
                    # save data should not be transferred or doesn't exist
                    next_node_success = await self.do_node_action(next_node_id, interaction_msg_or_context, None, event_object_class=event_object_class)
                    if next_node_success:
                        rc = 2
                    else:
                        rc = -3
        else:
            # next node is not valid or not loaded in. Just gonna ignore
            if not next_node_id:
                rc = 0
            else:
                rc = -1
            dialog_logger.debug("chaining found next node does not exist. stopping here")
        return rc

    async def handle_chaining(self, curr_active_node, next_node_id, end_progress_transfer, save_data, event_category, interaction_msg_or_context, event_object_class=None):
        '''deals with situations where there's a previous node and want to go to next_node_id. tries to go to next_node_id, then cleans up this node'''
        dialog_logger.info("started handling chaining from <%s> to next node <%s> end progres transfer? <%s>", curr_active_node.layout_node.id, next_node_id, end_progress_transfer)
        #TODO: future: implementing different ways of finishing handling interaction. can be editing message, sending another message, or sending a modal
        #       would like to specify in yaml if edit or send new message to finish option, modals have been mostly implemented
        #TODO: future: better directing flow so that this can borrow a dialog from another dialog flow and stay on this one without needing to define a copy 
        #       of an existing dialog just so that we can go to a different dialog
        if not event_object_class:
            event_object_class = type(interaction_msg_or_context).__name__
        
        # reference to who interacted this time.
        if event_object_class == "Interaction":
            interacting_user = interaction_msg_or_context.user
        else:
            interacting_user = interaction_msg_or_context.author
        
        goto_status = await self.goto_node(next_node_id, end_progress_transfer, save_data, interaction_msg_or_context, event_object_class)

        if goto_status < 0:
            # getting next node done failed, do updates to indicate failed
            dialog_logger.info("chaining from <%s> to next node <%s> failed", curr_active_node.layout_node.id, next_node_id)
            if event_object_class == "Interaction" and not interaction_msg_or_context.response.is_done():
                await interaction_msg_or_context.response.send_message(content="can't move to next step", ephemeral=True)
            else:
                await interaction_msg_or_context.channel.send(content="can't move to next step")
        else:
            # getting next node done succeeded, do updates to indicate success
            if event_object_class == "Interaction" and not interaction_msg_or_context.response.is_done():
                # safety net. should only activate if node didn't reply already. Just here so that it doesn't get confusing because discord will 
                # pop up a interaction failed if it isn't responded to
                await interaction_msg_or_context.response.send_message(content="interaction complete", ephemeral=True)

            dialog_logger.info("chaining from <%s> to next node <%s> succeeded.", curr_active_node.layout_node.id, next_node_id)

        # regardless of success or failing sending next node, maybe want to close this node.
        # first give node an update about how chaining went and where to, node can store changes
        # then try close
        await curr_active_node.post_chaining(goto_status, self.nodes[next_node_id] if next_node_id and next_node_id in self.nodes else None)
        if await curr_active_node.can_close():
            dialog_logger.debug("closing node after chaining from <%s> to next node <%s>.", curr_active_node.layout_node.id, next_node_id)
            await self.close_node(curr_active_node)
        elif end_progress_transfer and curr_active_node.save_data:
            dialog_logger.debug("cleaning becuase of end progress")
            for prev_node in curr_active_node.save_data["prev_nodes"]:
                if (interacting_user.id, prev_node) in self.flow_progress:
                    del self.flow_progress[(interacting_user.id, prev_node)]
        

        dialog_logger.debug("end of handling chaning all stored flow information <%s>", ["("+str(k)+":"+str(id(v))+")" for k,v in self.flow_progress.items()])
        self.print_detailed_saved_data()
        
    '''################################################################################################
    #
    #                                           EVENT LISTENING SECTION
    #
    ################################################################################################'''

    async def on_message(self, message: discord.Message):
        # first step is fintering for messages that are the answers to reply nodes. only ones we care about here
        if "reply" not in self.waiting_categories or not message.reference or (not message.reference.message_id in self.waiting_categories["reply"]):
            dialog_logger.debug("message reference is <%s>, is reply in waiting cats? <%s>,  is message id in waiting? <%s>", message.reference, "reply" in self.waiting_categories, message.reference.message_id in self.waiting_categories["reply"] if message.reference and "reply" in self.waiting_categories else "N/A")
            return
        interacted_node = self.waiting_categories["reply"][message.reference.message_id]

        if not await interacted_node.filter_event(message):
            dialog_logger.debug("handling reply message, found active node memory address <%s> for node id <%s> and event does not pass filtering", 
                                id(interacted_node), interacted_node.layout_node.id)
            return
        dialog_logger.debug("found reply node memory address <%s> node id <%s> message id <%s>. save data attached <%s>, waiting for <%s>", 
                                id (interacted_node), interacted_node.layout_node.id, interacted_node.channel_message.id if interacted_node.channel_message else "N/A", interacted_node.save_data, interacted_node.waits)
        
        await self.handle_graph_event(interacted_node, message, "reply", type(message).__name__)

        dialog_logger.debug("end of handler on message handling in-channel reply message")

    async def on_interaction(self, interaction):
        '''custom system for filtering all relevant interactions. needs to be added to bot as listener.
        Currently used as a workaround to how Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id'''
        if interaction.type == InteractionType.modal_submit:
            if not "modal_submit" in self.waiting_categories:
                return
            if not (interaction.user.id, interaction.message.id) in self.waiting_categories["modal_submit"]:
                return
            dialog_logger.debug("on interaction found relavant modal submit interaction. interaction id <%s>, message id <%s>", 
                                interaction.id, interaction.message.id)
            await self.waiting_categories["modal_submit"][(interaction.user.id, interaction.message.id)].modal.do_submit(interaction)
        if interaction.type == InteractionType.component:
            if not "interaction" in self.waiting_categories:
                return
            if not interaction.message.id in self.waiting_categories["interaction"]:
                dialog_logger.debug("on interaction found not active: interaction id <%s> message id <%s>", 
                                interaction.id, interaction.message.id)
                return
            active_node = self.waiting_categories["interaction"][interaction.message.id]
            if not active_node.view:
                return
            if not await active_node.view.interaction_check(interaction):
                return
            dialog_logger.debug("on interaction found relavant component interaction, interaction id <%s> message id <%s>", 
                                interaction.id, interaction.message.id)
            option = interaction.data['custom_id']
            view = active_node.view
            # custom ids should be unique amonst items in a view so this should only ever return one item
            disc_item = [x for x in view.children if x.custom_id == option][0]             
            await disc_item.do_callback(interaction)

    '''################################################################################################
    #
    #                                       CLOSING NODES SECTION
    #
    ################################################################################################'''

    async def clean_clickables(self, open_dialog=None, progress=None, interaction=None):
        # print("clean clickables, passed in dialog", open_dialog)
        view = open_dialog.view
        # view.clear_items()
        await view.stop()
        # await data["message"].edit(view=view)
        # del self.message_status[data["message"].id]

    async def close_node(self, active_node, fulfilled=True):
        '''closes an open (ie waiting for data) instance of a node. removes any tracking data about it from stores 
        and modifies message in Discord if needed   
        conceptually, nodes defined in yaml create blueprint of a graph to travel, a sent message becomes instance of someone traversing
        that graph. closing instances is stopping person from walking not modifying graph.

        Parameters
        ---
        active_listner_key
            the key to access node data in stored active nodes. currently ususally message id
        fulfilled
            whether or not node was completed when it was closed. Can be used to differentiate what to show in those different cases.
            mostly used only for editing prompt of reply node to say "sorry we're closed" if it closed before reply was made
        '''
        dialog_logger.info("closing active node. node memory address <%s> node id <%s> message id <%s> was the response fulfilled? <%s>", 
                           id(active_node), active_node.layout_node.id, active_node.channel_message.id if active_node.channel_message else "N/A", fulfilled)
        # let node do own cleanup for whatever specialized functions it has
        if active_node.is_active:
            await active_node.close(fulfilled)
        # remove from all active and progress trackers
        for waiting in active_node.waits:
            if waiting in self.waiting_categories:
                if waiting == "modal_submit":
                    if (active_node.save_data["user"].id, active_node.layout_node.id) in self.waiting_categories[waiting]:
                        del self.waiting_categories[waiting][(active_node.save_data["user"].id, active_node.layout_node.id)]
                elif waiting == "automatic":
                    try:
                        self.waiting_categories[waiting].remove(active_node)
                    except Exception:
                        # TODO: currently not being added to this so this may cause an error. needs better handling, maybe decide what to do so don't need a try except
                        pass
                else:
                    if active_node.channel_message and active_node.channel_message.id in self.waiting_categories[waiting]:
                        del self.waiting_categories[waiting][active_node.channel_message.id]
            dialog_logger.debug("removing active node <%s> message id <%s> from waiting for <%s>.", 
                                id(active_node), active_node.channel_message.id if active_node.channel_message else "N/A", waiting)
        try:
            self.active_nodes.remove(active_node)
            dialog_logger.debug("removing active node <%s> message id <%s> from list of active nodes, remaining nodes <%s>", 
                                id(active_node), active_node.channel_message.id if active_node.channel_message else "N/A", [id(x) for x in self.active_nodes])
        except ValueError as e:
            dialog_logger.warn("close node trying to remove node that isn't listed as active here. ignoring")
            pass
        save_data = active_node.save_data
        if save_data and active_node.layout_node.id == save_data["curr_node"]:
            # clear out all save data if we're closing the node at the end of progress chain. Currently useful because it would hang until bot is restarted
            # and prevent redoing those nodes and there isn't anything to come back and check later. future versions may not want to immediately delete this
            # and if multiple nodes are allowed to be on same "step" of progress would break this logic
            user = save_data["user"]
            for prev_node_id in save_data["prev_nodes"]:
                try:
                    del self.flow_progress[(user.id, prev_node_id)]
                except Exception as e:
                    pass
        dialog_logger.debug("closing node also might have touched flow progress. stored stuff now: <%s>", ["("+str(k)+":"+str(id(v))+")" for k,v in self.flow_progress.items()])
        self.print_detailed_saved_data()

    '''################################################################################################
    #
    #                                       CLEANING DATA SECTION
    #
    ################################################################################################'''

    async def clean_task(self, delay, prev_task):
        # keep a local reference as shared storage can be pointed to another place
        this_cleaning = self.cleaning_task
        # dialog_logger.debug("clean task starting sleeping handler id <%s> task id <%s>", id(self), id(this_cleaning))

        # first sleep because this should only happen every x seconds
        await asyncio.sleep(delay)
        starttime = datetime.utcnow()
        if not self.cleaning_task:
            # last catch for task canceled in case it happened while sleeping. don't need to continue cleaning. not likely to hit this line.
            dialog_logger.info("seems like cleaning task already cancled. handler id <%s>, task id <%s>", id(self), id(this_cleaning))
            return
        #TODO: future: this setup means cleaning actually happens every max(how long clean takes, clean_freq_secs) seconds. may want to change it so
        #       it is always around clean_freq_secs
        try:
            await self.clean(this_cleaning)
            sleep_secs = max(0, (timedelta(seconds=self.clean_freq_secs) - (datetime.utcnow() - starttime)).total_seconds())
            # tasks are only fire once, so need to set up the next round
            self.cleaning_task = asyncio.get_event_loop().create_task(self.clean_task(sleep_secs, this_cleaning))
            # dialog_logger.debug("cleaning task <%s> set up next task call <%s>", id(this_cleaning), id(self.cleaning_task))
        except Exception as e:
            # last stop catch for exceptions just in case, otherwise will not be caught and aysncio will complain of unhandled exceptions
            dialog_logger.warning("cleaning run for handler id <%s> at time <%s> failed. no more cleaning. error: <%s>", id(self), starttime, e)


    #NOTE: FOR CLEANING ALWAYS BE ON CAUTIOUS SIDE AND DO TRY EXCEPTS ESPECIALLY FOR CUSTOM HANDLING. maybe should throw out some data if that happens?
    async def clean(self, this_clean_task):
        # dialog_logger.debug("doing cleaning action. handler id <%s> task id <%s>", id(self), id(this_clean_task))
        # clean out old data from internal stores
        now = datetime.utcnow()
        timed_out_nodes = []
        for active_node in self.active_nodes:
            if hasattr(active_node, "timeout"):
                if active_node.timeout < now:
                    timed_out_nodes.append(active_node)

        await asyncio.gather(*[self.close_node(node, False) for node in timed_out_nodes])
        # await asyncio.sleep(4)
        # dialog_logger.debug("finished cleaning task,  task id <%s>", id(this_clean_task))
        # maybe do a loop through flow_progress? currently close node does clean it but it also is a bit more aggressive about it than needed

        # await asyncio.gather(*[self.handle_graph_event(node, None, "automatic", "N/A") for node in self.waiting_categories["automatic"]])
        # await asyncio.gather(*[self.close_node(node, None, "automatic", "N/A") for node in self.waiting_categories["automatic"]])
        if DialogHandler.testing_cleaning_mode:
            choice = random.randint(0,2)
            dialog_logger.debug("choice <%s>", choice)
            if choice:
                raise Exception("testing exception")


    def start_cleaning(self, event_loop):
        'method to get the repeating cleaning task to start'
        random.seed(2)
        self.cleaning_task = event_loop.create_task(self.clean_task(self.clean_freq_secs, None))
        dialog_logger.info("starting cleaning handler id <%s> task id <%s>", id(self), id(self.cleaning_task))

    def stop_cleaning(self):
        dialog_logger.info("stopping cleaning handler id <%s> task id <%s>", id(self), id(self.cleaning_task))
        self.cleaning_task.cancel()
        self.cleaning_task = None

# since the interaction send_message doesn't return message that was sent by default, wrapper to get that behavior to be same as channel.send()
def interaction_send_message_wrapper(interaction):
    '''wrapper for sending a message to respond to interaction so that the message just sent is returned'''
    async def inner(**kwargs):
        await interaction.response.send_message(**kwargs)
        return await interaction.original_response()
    return inner

#custom button to always direct clicks to the handler because all information is there
class DialogView(ui.View):
    def __init__(self, handler, node_id, **kwargs):
        super().__init__(**kwargs)
        self.dialog_handler = handler
        self.node_id = node_id
        dialog_logger.debug("Dialog view initialized object memory address <%s> node id <%s>", id(self), node_id)

        dialog = self.dialog_handler.nodes[node_id]
        for op_id, option in dialog.options.items():
            self.add_item(DialogButton(self.dialog_handler, label=option.label, custom_id=option.id))

    def mark_active_node(self, active_node):
        self.active_node = active_node
    
    async def on_timeout(self):
        dialog_logger.debug("Dialog view on timeout callback, object memory address <%s> message id <%s> node id <%s>", 
                            id(self), self.active_node.channel_message.id if self.active_node.channel_message else "N/A", self.node_id)
        await super().on_timeout()
        if self.active_node:
            await self.dialog_handler.close_node(self.active_node, fulfilled=False)

    async def stop(self):
        dialog_logger.info("Dialog view stopped. object memory address <%s> message id <%s> node id <%s>", id(self), self.active_node.channel_message.id if self.active_node.channel_message else "N/A", self.node_id)
        super().stop()

    def __del__(self):
        dialog_logger.debug("dialog view <%s> has been destroyed", id(self))

class DialogButton(ui.Button):
    def __init__(self, handler, **kwargs):
        # print("dialogButton init internal", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler
        dialog_logger.debug("Dialog button initialized, object memory address <%s>", id(self))

    async def do_callback(self, interaction):
        '''renamed from default callback function. Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id, so a custom callback system is used. Workaround for now is
        for handler to find the right button to callback and rename function so regular system doesn't cause double calls on a single event'''
        dialog_logger.debug("Dialog button clicked. interaction id <%s> message id <%s> view object memory address <%s> raw data in <%s> node id <%s>", 
                            interaction.id, interaction.message.id, id(self.view), interaction.data, self.view.node_id)
        interaction.extras["node_id"] = self.view.node_id
        await self.dialog_handler.find_interacted_node(interaction)

    def __del__(self):
        dialog_logger.debug("dialog button <%s> has been destroyed", id(self))

class DialogSelect(ui.Select):
    def __init__(self, handler, **kwargs):
        # print("DialogSelect init", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler

    async def callback(self, interaction):
        interaction.extras["node_id"] = self.view.node_id
        await self.dialog_handler.find_interacted_node(interaction)

class DialogModal(ui.Modal):
    def __init__(self, handler, node_id, **kwargs) -> None:
        self.dialog_handler = handler
        modal_info = self.dialog_handler.nodes[node_id]
        super().__init__(**kwargs, title=modal_info.title, custom_id=node_id)
        self.node_id = node_id

        for field_id, field in modal_info.fields.items():
            self.add_item(ui.TextInput(label=field.label, custom_id=field.label, default=field.default_value,
                                       max_length=field.max_length, min_length=field.min_length, placeholder=field.placeholder,
                                       required=field.required, style=field.style))

    async def do_submit(self, interaction):
        '''renamed from default on_submit function. Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id, so a custom callback system is used. Workaround for now is
        for handler to find the right button to callback and rename function so regular system doesn't cause double calls on a single event'''
        interaction.extras["node_id"] = self.node_id
        dialog_logger.debug("modal submitted. node id <%s> submitted data <%s> interaction message <%s>", 
                            self.node_id, interaction.data, interaction.message.id)
        await self.dialog_handler.find_interacted_node(interaction)

    async def on_timeout(self):
        # seems like default for modals is nevr time out?
        dialog_logger.debug("modal <%s> timed out", self.node_id)

    def __del__(self):
        dialog_logger.debug("dialog modal <%s> has been destroyed", id(self))

async def submit_results(open_dialog=None, progress=None, interaction=None):
    #NOTE: VERY ROUGH RESULT MESSAGE JUST FOR PROOF OF CONCEPT THAT DATA WAS STORED. MUST BE EDITED ONCE FORMAT IS FINALIZED (yes its messy)
    await interaction.channel.send("questionairre received "+progress["data"]["questionairre_name"])