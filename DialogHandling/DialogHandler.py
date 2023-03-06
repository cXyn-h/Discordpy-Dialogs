import yaml
import inspect
import discord
from discord import ui, InteractionType, Interaction
from DialogHandling.DialogObjects import *
import DialogHandling.DialogNodeParsing as DialogNodeParsing

import logging
import sys
dialog_logger = logging.getLogger('Dialog Handler')
dialog_logging_handler = logging.StreamHandler(sys.stderr)
dialog_logging_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
dialog_logging_handler.setFormatter(dialog_logging_format)
dialog_logger.addHandler(dialog_logging_handler)
dialog_logger.setLevel(logging.INFO)
# WIP alpha version, will have tons of logging printout and unfinished areas.

#TODO: variable content of message: grab at run not from file
#TODO: implement save and load stored data about what's in progress
#       at least having on_interaction helps with hanging buttons on previous messages that were sent before restart,
#       but this would ensure any advanced filters on those would be saved through restart
#TODO: handle view timeouts better, save data isn't cleaned up, but is that needed?
#TODO: handle interaction needs to check in with active listeners and if that now needs to be deactivated 
#       and maybe custom limits like max number of reactors instead of built in view timeout
#TODO: Figure out what sorts of data get passed into callbacks
#       currently: dialog callbacks won't have progress or interaction ones
#       callbacks from interactions hve interaction, and progress if data has been added
#TODO: filters for who can interact with nodes for other types of nodes, also more advanced filters
#TODO: switching where next message will be sent
#TODO: apparently created modals don't get garbage collected once they're submitted, it only seems to happen once the program ends
#TODO: custom defined nodes?
#TODO: program-makes-a-choice-instead-of-waiting-for-user node
#TODO: using next step flag to indicate when one stage is completed might help?
#TODO: fixing logic to support multiple people: filtering who is allowed to hit buttons on dialog to progress data
#TODO: chaining, dealing with error of having node after flow progress is saved, and what happens when you re-enter that node with flow progress still active

class DialogHandler():
    # passing in dialogs and callbacks if you want them shared between instances. not tested yet
    def __init__(self, nodes = {}, callbacks = {}) -> None:
        self.nodes = nodes
        self.callbacks = callbacks
        #TODO: these probably need something that enforces certain structure to anything put inside
        #TODO: both need a once over to make sure things are cleaned up properly during timeouts, errors, dropped messages, bot crashes, regular stuff etc.
        self.active_listeners = {"modals":{}}
        self.flow_progress = {}
        # some default available items
        self.register_dialog_callback(self.clean_clickables)
        self.register_dialog_callback(submit_results)
        # this dialog might not be used in future
        self.nodes["default_completed"] = DialogNodeParsing.parse_node({"id":"default_completed", "prompt":"completed"})

    '''################################################################################################
    #
    # LOAD FROM FILE METHODS
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
        #TODO: function goes through all loaded dialog stuff to make sure it's valid. ie all items have required parems, 
        #       parems are right format, references point to regestered commands and dialogs, etc
        pass

    # this makes it eaiser, one spot to find all functions. and also good for security against bad configs
    def register_dialog_callback(self, func):
        '''adds passed in function to list of functions that are ok to be callback functions. Can be coroutines'''
        #TODO: check not register function and how to make callbacks unmodifiable/inaccessible from outside?
        self.callbacks[func.__name__] = func

    def build_clickables(self, dialog_name):
        '''not meant to be called currently, the add items already in init of view. create the object handling the interactable buttons you can click '''
        dialog = self.nodes[dialog_name]
        view = DialogView(self, dialog_name)
        # testing how a selector works. sort of works with current setup, selector might need a custom id, and value is what is passed 
        #   to indicate which one was selected
        # selector=DialogSelect(self)
        for op_id, option in dialog.options.items():
            # selector.add_option(label=option.label, value=option.id)
            view.add_item(DialogButton(self, label=option.label, custom_id=option.id))
        # view.add_item(selector)
        # print("build clickables", "for dialog", dialog_name, "children memory addresses", str([id(child) for child in view.children]), "address of view", id(view))
        return view

    def build_modal(self,modal_name):
        '''not meant to be called currently, the add items already in init of modal'''
        modal_info = self.nodes[modal_name]
        modal = DialogModal(self, modal_name)
        for field in modal_info.fields.values():
            modal.add_item(ui.TextInput(self, label=field.label, custom_id=field.id))
        return modal

    async def execute_command_callback(self, command_name, **kwargs):
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
            dialog_logger.error("callback name <%s> not found", command_name)
   
    def print_detailed_saved_data(self):
        '''only for debugging purposes. prints out long form information about stored state'''
        indent = "   "
        if len(self.active_listeners) > 0:
            dialog_logger.debug(f"{indent}recorded nodes awaiting responses")
            for node_message_id, save in self.active_listeners.items():
                if node_message_id == "modals":
                    for modal_message_id, modal_data in save.items():
                        dialog_logger.debug(f"{indent}{indent}msg id: <{modal_message_id}> node id<{modal_data['modal'].node_name}> type: modal finished? <{modal_data['modal'].is_finished()}>")
                else:
                    view_info = ("view finished? <"+str(save["view"].is_finished()) + "> object memory address <" + str(id(save["view"])) + "> view message id <"+str(save["view"].message.id) +">" if "view" in save else "")
                    dialog_logger.debug(f"{indent}{indent}msg id <{node_message_id}> node id <{save['node_name']}> {view_info} all keys {save.keys()}")
        else:
            dialog_logger.debug(f"{indent}no recorded nodes awaiting responses")
        
        if len(self.flow_progress) > 0:
            dialog_logger.debug(f"{indent}recorded save progress")
            for k,v in self.flow_progress.items():
                reply_submit_info = ",".join(["{node id "+ node_id + "content "+ str(submission.content)+"}" for node_id,submission in v["reply_submits"].items()]) if "reply_submits" in v else ""
                modal_submit_info = ",".join(["{node id "+ node_id + "content "+ str(submission)+"}" for node_id,submission in v["modal_submits"].items()]) if "modal_submits" in v else ""

                dialog_logger.debug(f"{indent}{indent}user id <{k[0]}> node id <{k[1]}> recorded type <{v['type']}> {'flag<'+v['flag']+'>' if 'flag' in v else ''} previous nodes <{v['prev_nodes']}> all keys <{v.keys()}>")
                if "reply_submits" in v:
                    dialog_logger.debug(f"{indent}{indent}{indent}reply submit values")
                    dialog_logger.debug(f"{indent}{indent}{indent}{reply_submit_info}")
                if "modal_submits" in v:
                    dialog_logger.debug(f"{indent}{indent}{indent}modal submit values")
                    dialog_logger.debug(f"{indent}{indent}{indent}{modal_submit_info}")
        else:
            dialog_logger.debug(f"{indent}no recorded flow progress")

    def print_compact_saved_data(self):
        '''only for debugging purposes. prints out a more compact form information about stored state'''
        open_dialog_info = ", ".join(["{id:"+str(message_id)+ " dialog:"+save["node_name"]+"}" for message_id, save in self.active_listeners.items() if message_id != "modals"])
        dialog_logger.debug(f"non modal nodes awaiting responses {open_dialog_info}")
        open_dialog_info = ", ".join(["{id:"+str(message_id)+ " dialog:"+save["node_name"]+"}" for message_id, save in self.active_listeners["modals"].items()])
        dialog_logger.debug(f"modal nodes awaiting responses (this one is a bit bugged) {open_dialog_info}")
        dialog_logger.debug(f"open flow progress {self.flow_progress.keys()}")


    '''################################################################################################
    #
    # SENDING NODES METHODS
    #
    ################################################################################################'''

    # Likely not using in future. Also want to manage rest of sending and taking care of callbacks/data when sending new dialog so this doesn't cover enough
    # def register_open_dialog(self, message, dialog_name, view, data={}):
    #     self.message_status[message.id] = {**data, "dialog_name":dialog_name, "message":message, "view":view}
    
    async def send_dialog(self, dialog_id, interaction_msg_or_context, passed_in_type, msg_options={}):
        '''
        When you need to send a new message that contains dialog with options to choose. Handles sending, adding data to tracking, and dialog callbacks
        Parem
        -----
        send_method - coroutine
            reference to function to call to send a message. should already point to destination, and message and other options can be passed in.
            Must return the resulting message that was just sent, so if its an interaction response use the wrapper in this file
        '''
        dialog_logger.info("dialog handler start of send dialog. dialog id: <%s> context-giving object type: <%s> memory address of context-giving object: <%s> %s", 
                            dialog_id, passed_in_type, id(interaction_msg_or_context),"interaction id "+str(interaction_msg_or_context.id) if passed_in_type == "interaction" else "")
        #TODO: add option to add data to dialog objects, data only saved with the message, not passed into the saved progress
        dialog_info = self.nodes[dialog_id]
        send_method = interaction_send_message_wrapper(interaction_msg_or_context) \
                        if passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        #TODO: handle edge cases of 0, 1, > number of button slots options
        if len(dialog_info.options) > 0:
            view = DialogView(self, dialog_id)
            dialog_message = await send_method(content=dialog_info.prompt, view=view, **msg_options)
            view.mark_message(dialog_message)
            self.active_listeners[dialog_message.id] = {"node_name": dialog_id, "view":view, "message":dialog_message, "type":"dialog"}
            dialog_logger.debug("creating view and sending message. added info: message id: <%s> dialog id: <%s> memory address of view: <%s> view children memory addresses: <%s>", 
                                self.active_listeners[dialog_message.id]['message'].id, self.active_listeners[dialog_message.id]['node_name'],
                                id(self.active_listeners[dialog_message.id]['view']), str([id(child) for child in view.children]))
        else:
            # not clear how to handle only one option listed 
            dialog_message = await send_method(content=dialog_info.prompt, **msg_options)
            self.active_listeners[dialog_message.id] = {"node_name": dialog_id, "view":None, "message":dialog_message, "type":"dialog"}
            dialog_logger.debug("zero option dialog, sending message only message id <%s> dialog id <%s>",
                                self.active_listeners[dialog_message.id]['message'].id, self.active_listeners[dialog_message.id]['node_name'])

        # do the command for the dialog
        if dialog_info.command:
            await self.execute_command_callback(dialog_info.command, open_dialog=self.active_listeners[dialog_message.id] if dialog_message.id in self.active_listeners else {})

        # if there are fewer than 1, then we really aren't waiting for a choice to be made so dialog not really open anymore.
        #TODO: maybe don't even do this dance of adding and removing for the callback if there aren't any options? why would this be needed?
        if len(dialog_info.options) < 1:
            dialog_logger.debug("dialog has zero options, removing it from tracking. message id <%s> dialog id <%s>",
                                self.active_listeners[dialog_message.id]['message'].id, self.active_listeners[dialog_message.id]['node_name'])
            await self.close_node(dialog_message.id, "dialog")
        dialog_logger.info("dialog handler end of send dialog")
        return dialog_message

    # thinking needed a separate method for this but seems still simple one line thing so it's still in handle interaction
    async def send_modal(self, node_id, interaction):
        dialog_logger.info("dialog handler start of send modal node id: <%s> interaction id: <%s> message id: <%s>", node_id, interaction.id, interaction.message.id)
        modal_info = DialogModal(self, node_id)

        await interaction.response.send_modal(modal_info)

        if "modals" not in self.active_listeners:
            # message id for button interactions seem to be message the button is on, which can conflict with recorded info for dialog nodes
            # so I guess seperate section for modals?
            self.active_listeners["modals"] = {}
        if interaction.message.id in self.active_listeners["modals"]:
            #TODO: This check doesn't work. more than one modal can happen from same message for different people and both are valid
            # dialogs are always new message so don't need this check. modals can be triggered by a message that stays and thus be re-added
            await self.close_node(interaction.message.id, "modal")
            dialog_logger.error("send modal found modal already existed for this message id <%s> it is now replaced", interaction.message.id)
        self.active_listeners["modals"][interaction.message.id] = {"node_name":node_id, "modal":modal_info, "message":interaction.message, "type":"modal"}
        dialog_logger.info("end of send modal node id: <%s> interaction id: <%s> memory address of modal %s",
                node_id, interaction.id, id(modal_info))

    async def send_reply_node(self, node_id, interaction_msg_or_context, passed_in_type, msg_opts={}):
        dialog_logger.info("dialog handler start of sending reply node node id: <%s> memory address of context-giving object <%s> type of context-giving object: <%s>",
                node_id, id(interaction_msg_or_context), passed_in_type)

        reply_node_info = self.nodes[node_id]
        msg_contents = reply_node_info.prompt if reply_node_info.prompt else "Please type response in chat"
        send_method = interaction_send_message_wrapper(interaction_msg_or_context) if \
                        passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        prompt_message = await send_method(content=msg_contents, **msg_opts)
        #TODO: fancier filters
        #TODO: need a timeout for waiting for replies?
        #TODO: automatic add a cancel button? or allow options on the node?
        self.active_listeners[prompt_message.id] = {"node_name": node_id, "message":prompt_message, "filters":{}, "type":"reply"}
        if passed_in_type == "interaction":
            self.active_listeners[prompt_message.id]["filters"].update({"channel":interaction_msg_or_context.channel.id, "user":interaction_msg_or_context.user.id})
        else:
            self.active_listeners[prompt_message.id]["filters"].update({"channel":interaction_msg_or_context.channel.id, "user":interaction_msg_or_context.author.id})
        dialog_logger.info("end of sending reply node node id <%s> message id <%s> recorded filters for this node: <%s>", 
                           node_id, prompt_message.id, self.active_listeners[prompt_message.id]['filters'])
        self.print_detailed_saved_data()

    async def do_node_action(self, node_name, interaction_msg_or_context, msg_opts = {}, passed_in_type = None):
        '''entry point for doing actions related to node itself'''
        dialog_logger.info("handler node action beginning node id <%s>", node_name)
        if not passed_in_type:
            # denote whether we were given an interaction obj to respond to and for context, context obj, or message obj for chaining.
            # having this passed around as well so this doesn't have to be recalculated
            passed_in_type = "interaction" if issubclass(type(interaction_msg_or_context), Interaction) else ("message" if isinstance(interaction_msg_or_context, discord.Message) else "context")
        if not node_name in self.nodes:
            dialog_logger.warning("node <%s> not laoded. skipping", node_name)
            return
        node_info = self.nodes[node_name]

        if node_info.type == "dialog":
            await self.send_dialog(node_name, interaction_msg_or_context, passed_in_type, msg_opts)
        elif node_info.type == "modal":
            if not issubclass(type(interaction_msg_or_context), Interaction):
                raise Exception("Invalid state. dialog handler next node is a modal, was passed a context when it must be an interaction")
            await self.send_modal(node_name, interaction_msg_or_context)
        elif node_info.type == "reply":
            await self.send_reply_node(node_name, interaction_msg_or_context, passed_in_type)
        dialog_logger.info("end of node action")

    '''################################################################################################
    #
    # RESPONDING TO CHOICES AND CHAINING NODES
    #
    ################################################################################################'''

    async def handle_interaction(self, interaction):
        ''' handle clicks and interactions with message components on messages that are tracked as open dialogs. handles identifying which action it is, 
        callback for that interaction, and sending the next dialog in the flow'''
        dialog_logger.info("dialog handler start handling interaction interaction id: <%s> message id: <%s> raw data in: <%s> interaction extras <%s>",
                           interaction.id, interaction.message.id, interaction.data, interaction.extras)

        # grab information needed to handle interaction on any supported node type
        node_info = self.nodes[interaction.extras["node_name"]]
        dialog_logger.debug("handle interaction found interaction <%s> is for node <%s>", interaction.id, node_info.id)
        saved_progress = None
        if (interaction.user.id, node_info.id) in self.flow_progress:
            saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
        next_node_name = None
        end_progress_transfer = None
        
        if interaction.type == InteractionType.modal_submit:
            dialog_logger.info("handle interaction modal submit branch")

            if not (interaction.user.id, node_info.id) in self.flow_progress:
                self.flow_progress[(interaction.user.id, node_info.id)] = {"node_name": node_info.id, "user":interaction.user, "prev_nodes":set()}
                saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
                dialog_logger.debug("interaction id <%s> message id <%s> added data", interaction.id, interaction.message.id)

            if node_info.data:
                if not "data" in saved_progress:
                    self.flow_progress[(interaction.user.id, node_info.id)]["data"] = {}
                self.flow_progress[(interaction.user.id, node_info.id)]["data"].update(node_info.data)
                dialog_logger.debug("handle interaction: interaction <%s> for node <%s> node has data <%s>", interaction.id, node_info.id, node_info.data)
            if node_info.flag:
                self.flow_progress[(interaction.user.id, node_info.id)]["flag"] = node_info.flag
                dialog_logger.debug("handle interaction: interaction <%s> for node <%s> node has flag <%s>", interaction.id, node_info.id, node_info.flag)
            
            self.flow_progress[(interaction.user.id, node_info.id)]["type"] = "modal"
            if "modal_submits" not in self.flow_progress[(interaction.user.id, node_info.id)]:
                self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"] = {}
            #TODO: saving modal submit information needs a bit of format finetuning
            self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"][node_info.id] = interaction.data["components"]
            dialog_logger.debug("dialog handler updated saved progres with modal submitted info <%s>", self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"])

            if node_info.submit_callback and node_info.submit_callback in self.callbacks:
                await self.execute_command_callback(node_info.submit_callback, 
                        open_dialog=None, 
                        progress=saved_progress, 
                        interaction=interaction)
            next_node_name = node_info.next_node
            end_progress_transfer = node_info.end
            dialog_logger.info("dialog hanlder finished modal submit branch node id: <%s> interaction id: <%s> is there saved progress: <%s>",
                    node_info.id, interaction.id, 'yes' if saved_progress else 'no')
        else:
            if not interaction.message.id in self.active_listeners:
                return
            # grabbing dialog specific information
            chosen_option = node_info.options[interaction.data["custom_id"]]
            dialog_logger.debug("found interaction on message <%s> is for dialog <%s> chosen option: <%s> next node info <%s>", 
                  interaction.message.id, node_info.id, chosen_option, chosen_option.next_node)
            dialog_logger.debug("cont. memory address of view for message <%s>",id(self.active_listeners[interaction.message.id]['view']))

            # update saved data because any flags and data from an option applies when that option is chosen
            if chosen_option.data or chosen_option.flag:
                # might not be any preexisting saved data, create it
                if not (interaction.user.id, node_info.id) in self.flow_progress:
                    dialog_logger.debug("save data added for user <%s> node <%s>, the option adds data", interaction.user.id, node_info.id)
                    self.flow_progress[(interaction.user.id, node_info.id)] = {"node_name": node_info.id, "user":interaction.user, "prev_nodes":set()}
                    saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
                else:
                    dialog_logger.debug("handle interaction found save data for %s", (interaction.user.id, node_info.id))
                self.flow_progress[(interaction.user.id, node_info.id)]["type"] = "dialog"
                if chosen_option.data:
                    if not "data" in saved_progress:
                        saved_progress["data"] = {}
                    saved_progress["data"].update(chosen_option.data)
                    dialog_logger.debug("handle interaction: interaction <%s> for node <%s> option has data <%s>, after update:<%s>", 
                                        interaction.id, node_info.id, chosen_option.data, self.flow_progress[(interaction.user.id, node_info.id)]["data"])
                if chosen_option.flag:
                    saved_progress["flag"] = chosen_option.flag
                    dialog_logger.debug("handle interaction: interaction <%s> for node <%s> option has flag <%s> after update:<%s>", 
                                        interaction.id, node_info.id, chosen_option.flag, self.flow_progress[(interaction.user.id, node_info.id)]["flag"])
            
            # handling callback stage
            if chosen_option.command:
                await self.execute_command_callback(chosen_option.command, 
                        open_dialog=self.active_listeners[interaction.message.id], 
                        progress=saved_progress, 
                        interaction=interaction)
                # await interaction.response.send_modal(Questionnaire())
            
            next_node_name = chosen_option.next_node
            end_progress_transfer = chosen_option.end

        # # handling interaction response and wrapping up stage
        await self.handle_chaining(node_info, next_node_name, end_progress_transfer, interaction, passed_in_type="interaction")
        dialog_logger.info("end handle interaction node id <%s> message id <%s>", node_info.id, interaction.message.id)
        if interaction.type == InteractionType.modal_submit:
            # once modal is submitted, don't need to track it anymore
            del self.active_listeners["modals"][interaction.message.id]
                        

    async def handle_chaining(self, curr_node, next_node_id, end_progress_transfer, interaction_msg_or_context, passed_in_type=None):
        dialog_logger.info("started handling chaining from <%s> to next node <%s> end progres transfer? <%s>", curr_node.id, next_node_id, end_progress_transfer)
        #TODO: implementing different ways of finishing handling interaction. can be editing message, sending another message, or sending a modal
        #       would like to specify in yaml if edit or send new message to finish option, modals have been mostly implemented
        #TODO: better directing flow so that this can borrow a dialog from another dialog flow and stay on this one without needing to define a copy 
        #       of an existing dialog just so that we can go to a different dialog
        if not passed_in_type:
            passed_in_type = "interaction" if issubclass(type(interaction_msg_or_context), Interaction) else ("message" if isinstance(interaction_msg_or_context, discord.Message) else "context")
        
        # set up variables to point to data since different incoming formats have different locations for data needed
        curr_node_message = interaction_msg_or_context
        if passed_in_type != "message":
            curr_node_message = interaction_msg_or_context.message

        if passed_in_type == "interaction":
            user = interaction_msg_or_context.user
        else:
            user = interaction_msg_or_context.author

        saved_progress = None
        if (user.id, curr_node.id) in self.flow_progress:
            saved_progress = self.flow_progress[(user.id, curr_node.id)]

        dialog_logger.debug('handling chaining memory address of context-giving object <%s> type of context-giving object: <%s> found saved data? <%s> interaction id: <%s>', 
                            id(interaction_msg_or_context), passed_in_type, 'yes' if saved_progress else 'no', interaction_msg_or_context.id if passed_in_type == 'interaction' else '')

        # print("handling chaining, finding basic data","user id", user.id,"curr_node", curr_node.id, "saved progress", saved_progress.keys() if saved_progress else "NONE", "all saved flow", self.flow_progress.keys())
        if next_node_id and not (next_node_id in self.nodes):
            dialog_logger.warning(f"warning, trying to chain from {curr_node.id} to {next_node_id} but next node not registered. ignoring and dropping for now, double check definitions.")

        if next_node_id in self.nodes:
            # next node is registered properly, means need to go to next node and deal with save data
            next_node = self.nodes[next_node_id]
            dialog_logger.info("handling chaining, next node found. type: <%s>", next_node.type)
            if next_node.type == "dialog":
                # TODO: assuming when need to progress is getting messy.
                #       some dialogs branch and need to transfer data, others do not. the guessing so far supports a help 
                #       button that prints out extra message, does not affect save state, and execute continues from message with help button
                if curr_node.type == "dialog" and saved_progress and curr_node_message.id in self.active_listeners and len(next_node.options) > 0:
                    dialog_logger.debug("chaining from dialog to dialog and requires cleanup of buttons on this message")
                    await self.clean_clickables(self.active_listeners[curr_node_message.id])
                await self.do_node_action(next_node_id, interaction_msg_or_context)
                if saved_progress:
                    if not end_progress_transfer and len(next_node.options) > 0:
                        dialog_logger.debug("chaining next node is dialog, and save data needs to be progressed")
                        self.flow_progress[(user.id, next_node_id)] = {**self.flow_progress[(user.id, curr_node.id)], "type":"dialog"}
                        self.flow_progress[(user.id, next_node_id)]["prev_nodes"].add(curr_node.id)
                        del self.flow_progress[(user.id, curr_node.id)]
                    if end_progress_transfer:
                        dialog_logger.debug("chaining next node is dialog, and save data needs ended")
                        del self.flow_progress[(user.id, curr_node.id)]
            elif next_node.type == "modal" or next_node.type == "reply":
                if curr_node.type == "dialog" and saved_progress and curr_node_message.id in self.active_listeners:
                    dialog_logger.debug("chaining from dialog to modal or reply and requires cleanup of buttons on this message")
                    await self.clean_clickables(self.active_listeners[curr_node_message.id])
                await self.do_node_action(next_node_id, interaction_msg_or_context)
                if saved_progress:
                    if not end_progress_transfer:
                        dialog_logger.debug("chaining to modal or reply and data needs to be transfered")
                        self.flow_progress[(user.id, next_node_id)] = self.flow_progress[(user.id, curr_node.id)]
                        self.flow_progress[(user.id, next_node_id)]["type"] = next_node.type
                        self.flow_progress[(user.id, next_node_id)]["prev_nodes"].add(curr_node.id)
                    del self.flow_progress[(user.id, curr_node.id)]
        else:
            # no next node, end of line so clean up
            dialog_logger.info("handling chaining, no next node.")
            if passed_in_type == "interaction":
                await interaction_msg_or_context.response.send_message(content="interaction completed", ephemeral=True)
            if saved_progress:
                    if curr_node.type == "dialog" and curr_node_message.id in self.active_listeners:
                        await self.clean_clickables(self.active_listeners[curr_node_message.id])
                    del self.flow_progress[(user.id, curr_node.id)]

        # final net for catching interactions to make it less confusing for user
        if passed_in_type == "interaction" and not interaction_msg_or_context.response.is_done():
            dialog_logger.warning("dialog handler handle chaining reached special interaction complete check node id: <%s> interaction id: <%s>", curr_node.id, interaction_msg_or_context.id)
            await interaction_msg_or_context.response.send_message(content="interaction completed", ephemeral=True)
        dialog_logger.info("dialog handler finished chainging")
        self.print_detailed_saved_data()

    async def on_message(self, message: discord.Message):
        # first step is fintering for messages that are the answers to reply nodes. only ones we care about here
        found_node_id = None
        node_message = None
        for listener in self.active_listeners.values():
            # print("active filter","node", listener["node_name"], "node type", self.nodes[listener["node_name"]].type, listener.keys())
            # active listeners may have entries for different types of nodes that are waiting for events.
            # only reply nodes matter here and they have a filters field stored
            if not "filters" in listener:
                continue

            if message.author.id == listener["filters"]["user"] and message.channel.id == listener["filters"]["channel"]:
                found_node_id = listener["node_name"]
                node_message = listener["message"]
                break

        # finished looking, either found the message fulfills a node's conditions or failed to find any 
        if not found_node_id:
            dialog_logger.debug("on message, message id <%s> contents <%s> is not reply to any reply nodes", message.id, message.content[:20])
            return

        # handle all actions about saving info and moving onto next step
        node_info = self.nodes[found_node_id]
        dialog_logger.debug("on message found valid in-chat reply message id: <%s> node id: <%s>", message.id, found_node_id)

        # assuming information sent via reply is like a form submit and should immediately be saved
        if not (message.author.id, node_info.id) in self.flow_progress:
            self.flow_progress[(message.author.id, node_info.id)] = {"node_name": node_info.id, "user":message.author, "prev_nodes":set()}
            dialog_logger.debug("reply added save data for user <%s> node <%s>", message.author.id, node_info.id)
        saved_progress = self.flow_progress[(message.author.id, node_info.id)]
        if node_info.flag:
            if not "data" in saved_progress:
                self.flow_progress[(message.author.id, node_info.id)]["data"] = {}
            self.flow_progress[(message.author.id, node_info.id)]["data"].update(node_info.data)
        if node_info.flag:
            self.flow_progress[(message.author.id, node_info.id)]["flag"] = node_info.flag

        saved_progress["type"] = "reply"
        if "reply_submits" not in saved_progress:
            saved_progress["reply_submits"] = {}
        #TODO: handle what happens during overwrite of this. probably is possible if you leave a dialog node that leads to this with its buttons there
        #       and keep hitting the button instead of replying? Becuase of for loop setup, if there's multiple reply nodes, they are handled one at a time
        saved_progress["reply_submits"][found_node_id] = message

        if node_info.submit_callback and node_info.submit_callback in self.callbacks:
            await self.execute_command_callback(node_info.submit_callback, 
                    open_dialog=self.active_listeners[node_message.id], 
                    progress=saved_progress, 
                    interaction=None)
        
        # message object is only needed for knowing who sent and where it was sent
        await self.handle_chaining(node_info, node_info.next_node, node_info.end, message)

        # assuming once there's one reply then this node is done listening, maybe fancier stuff like waiting for multiple replies in future
        await self.close_node(node_message.id, "reply", fulfilled=True)

        dialog_logger.debug("end of handler on message handling in-channel reply message")

    async def on_interaction(self, interaction):
        '''custom system for filtering all relevant interactions. needs to be added to bot as listener.
        Currently used as a workaround to how Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id'''
        if interaction.type == InteractionType.modal_submit:
            if not "modals" in self.active_listeners:
                return
            if not interaction.message.id in self.active_listeners["modals"]:
                return
            dialog_logger.debug("on interaction found relavant modal submit interaction. interaction id <%s>, message id <%s>", 
                                interaction.id, interaction.message.id)
            await self.active_listeners["modals"][interaction.message.id]["modal"].do_submit(interaction)
        if interaction.type == InteractionType.component:
            if not interaction.message.id in self.active_listeners:
                return
            listener = self.active_listeners[interaction.message.id]
            if not "view" in listener or not listener["view"]:
                return
            dialog_logger.debug("on interaction found relavant component interaction, interaction id <%s> message id <%s>", 
                                interaction.id, interaction.message.id)
            option = interaction.data['custom_id']
            view = listener["view"]
            # custom ids should be unique amonst items in a view so this should only ever return one item
            disc_item = [x for x in view.children if x.custom_id == option][0]             
            await disc_item.do_callback(interaction)

    async def clean_clickables(self, open_dialog=None, progress=None, interaction=None):
        # print("clean clickables, passed in dialog", open_dialog)
        view = open_dialog["view"]
        # view.clear_items()
        await view.stop()
        # await data["message"].edit(view=view)
        # del self.message_status[data["message"].id]

    async def close_node(self, active_listner_key, node_type, fulfilled=True):
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
        #TODO: maybe clean up flow progress as well?
        if node_type == "dialog":
            if active_listner_key in self.active_listeners:
                node_data = self.active_listeners[active_listner_key]
                view = node_data["view"]
                if view:
                    dialog_logger.debug("close_node acting on dialog with active view. message id: <%s> node id:<%s> saved node state data's keys <%s>", 
                                        active_listner_key, node_data['node_name'], node_data.keys())
                    view.clear_items()
                    await node_data["message"].edit(view=view)
                else:
                    dialog_logger.debug("close_node acting on dialog, no view. message id: <%s> node id:<%s> saved node state data's keys <%s>", 
                                        active_listner_key, node_data['node_name'], node_data.keys())
                del self.active_listeners[active_listner_key]
        elif node_type == "modal":
            if "modals" in self.active_listeners and active_listner_key in self.active_listeners["modals"]:
                dialog_logger.debug("close_node acting on modal. source message id: <%s> node id:<%s> saved node state data's keys <%s>",
                                    active_listner_key, self.active_listeners['modals'][active_listner_key]['node_name'], 
                                    self.active_listeners['modals'][active_listner_key].keys())
                del self.active_listeners["modals"][active_listner_key]
        elif node_type == "reply":
            node_data = self.active_listeners[active_listner_key]
            if not fulfilled:
                dialog_logger.debug("close_node acting on reply node, not fulfilled. message id: <%s> node id:<%s> saved node state data's keys <%s>", 
                                    active_listner_key, node_data['node_name'], node_data.keys())
                await node_data["message"].edit(content="responses are closed")
            else:
                dialog_logger.debug("close_node acting on reply node, is fulfilled. message id: <%s> node id:<%s> saved node state data's keys <%s>", 
                                    active_listner_key, node_data['node_name'], node_data.keys())
            del self.active_listeners[active_listner_key]
        dialog_logger.info("end of close node on message id: <%s> node id:<%s>", active_listner_key, node_data['node_name'])
        self.print_detailed_saved_data()

# since the interaction send_message doesn't return message that was sent by default, wrapper to get that behavior to be same as channel.send()
def interaction_send_message_wrapper(interaction):
    '''wrapper for sending a message to respond to interaction so that the message just sent is returned'''
    async def inner(**kwargs):
        await interaction.response.send_message(**kwargs)
        return await interaction.original_response()
    return inner

#custom button to always direct clicks to the handler because all information is there
class DialogView(ui.View):
    def __init__(self, handler, node_name, **kwargs):
        super().__init__(**kwargs)
        self.dialog_handler = handler
        self.node_name = node_name
        dialog_logger.debug("Dialog view initialized bject memory address <%s> node id <%s>", id(self), node_name)

        dialog = self.dialog_handler.nodes[node_name]
        for op_id, option in dialog.options.items():
            self.add_item(DialogButton(self.dialog_handler, label=option.label, custom_id=option.id))

    def mark_message(self, message):
        self.message = message
    
    async def on_timeout(self):
        dialog_logger.debug("Dialog view on timeout callback, object memory address <%s> message id <%s> node id <%s>", 
                            id(self), self.message.id, self.node_name)
        await super().on_timeout()
        await self.dialog_handler.close_node(self.message.id, "dialog")

    async def stop(self):
        dialog_logger.info("Dialog view stopped. object memory address <%s> message id <%s> node id <%s>", id(self), self.message.id, self.node_name)
        super().stop()
        await self.dialog_handler.close_node(self.message.id, "dialog")

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
                            interaction.id, interaction.message.id, id(self.view), interaction.data, self.view.node_name)
        interaction.extras["node_name"] = self.view.node_name
        await self.dialog_handler.handle_interaction(interaction)

    def __del__(self):
        dialog_logger.debug("dialog button <%s> has been destroyed", id(self))

class DialogSelect(ui.Select):
    def __init__(self, handler, **kwargs):
        # print("DialogSelect init", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler

    async def callback(self, interaction):
        interaction.extras["node_name"] = self.view.node_name
        await self.dialog_handler.handle_interaction(interaction)

class DialogModal(ui.Modal):
    def __init__(self, handler, node_name, **kwargs) -> None:
        self.dialog_handler = handler
        modal_info = self.dialog_handler.nodes[node_name]
        super().__init__(**kwargs, title=modal_info.title, custom_id=node_name)
        self.node_name = node_name

        for field_id, field in modal_info.fields.items():
            self.add_item(ui.TextInput(label=field.label, custom_id=field.label, default=field.default_value,
                                       max_length=field.max_length, min_length=field.min_length, placeholder=field.placeholder,
                                       required=field.required, style=field.style))

    async def do_submit(self, interaction):
        '''renamed from default on_submit function. Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id, so a custom callback system is used. Workaround for now is
        for handler to find the right button to callback and rename function so regular system doesn't cause double calls on a single event'''
        interaction.extras["node_name"] = self.node_name
        dialog_logger.debug("modal submitted. node id <%s> submitted data <%s> interaction message <%s>", 
                            self.node_name, interaction.data, interaction.message.id)
        await self.dialog_handler.handle_interaction(interaction)

    async def on_timeout(self):
        # seems like default for modals is nevr time out?
        dialog_logger.debug("modal <%s> timed out", self.node_name)

    def __del__(self):
        dialog_logger.debug("dialog modal <%s> has been destroyed", id(self))

async def submit_results(open_dialog=None, progress=None, interaction=None):
    #NOTE: VERY ROUGH RESULT MESSAGE JUST FOR PROOF OF CONCEPT THAT DATA WAS STORED. MUST BE EDITED ONCE FORMAT IS FINALIZED (yes its messy)
    await interaction.channel.send("questionairre received "+progress["modal_submits"]["questionairreModal"][0]["components"][0]["value"])