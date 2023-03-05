import yaml
import inspect
import discord
from discord import ui, InteractionType, Interaction
from DialogHandling.DialogObjects import *

# WIP alpha version, will have tons of logging printout and unfinished areas.

#TODO: variable content of message: grab at run not from file
#TODO: support different ways to show options to select from?
#       support dropdown selection menus elements
#       option to not send as interactable buttons/selectors - such as wait for image reply
#TODO: implement save and load stored data about what's in progress
#       at least having on_interaction helps with hanging buttons on previous messages that were sent before restart,
#       but this would ensure any advanced filters on those would be saved through restart
#TODO: handle view timeouts better, save data isn't cleaned up, but is that needed?
#TODO: handle interaction needs to check in with active listeners and if that now needs to be deactivated 
#       and maybe custom limits like max number of reactors instead of built in view timeout
#TODO: finishing modal obj definitions
#TODO: Figure out what sorts of data get passed into callbacks
#       currently: dialog callbacks won't have progress or interaction ones
#       callbacks from interactions hve interaction, and progress if data has been added
#TODO: filters for who can interact with nodes for other types of nodes, also more advanced filters
#TODO: switching where next message will be sent
#TODO: apparently created modals don't get garbage collected once they're submitted, it only seems to happen once the program ends
#TODO: support flag and data for reply and modal nodes?
#TODO: custom defined nodes?
#TODO: program-makes-a-choice-instead-of-waiting-for-user node
#TODO: using next step flag to indicate when one stage is completed might help?
#TODO: redoing parsing to not care about handler instance in the middle of it
#TODO: fixing logic to support multiple people: filtering who is allowed to hit buttons on dialog to progress data

class DialogHandler():
    # passing in dialogs and callbacks if you want them shared between instances. not tested yet
    def __init__(self, nodes = {}, callbacks = {}) -> None:
        self.nodes = nodes
        self.callbacks = callbacks
        #TODO: these probably need something that enforces certain structure to anything put inside
        #TODO: both need a once over to make sure things are cleaned up properly during timeouts, errors, dropped messages, bot crashes, regular stuff etc.
        self.active_listeners = {}
        self.flow_progress = {}
        # some default available items
        self.register_dialog_callback(self.clean_clickables)
        self.register_dialog_callback(submit_results)
        # this dialog might not be used in future
        self.nodes["default_completed"] = self.parse_node({"id":"default_completed", "prompt":"completed"})

    '''################################################################################################
    #
    # LOAD FROM FILE METHODS
    #
    ################################################################################################'''

    def parse_node(self, yaml_node):
        '''creates and returns the Info object for each node. raises exception when data is missing'''
        #TODO: more edgecase and format guards for loading files
        if (not "id" in yaml_node):
            # basically all loaded nodes must have a id
            raise Exception("node missing id: "+ str(yaml_node))

        if yaml_node["id"] in self.nodes:
            raise Exception("node \""+yaml_node["id"]+"\" has been redefined. 2nd definition: "+ str(yaml_node))

        # yaml definition needs a type flag to specify if it is not a dialog node
        if "type" in yaml_node and yaml_node["type"] == "modal":
            if (not "title" in yaml_node):
                # basically all modals must have a separate title to display to all interacters
                raise Exception("modal node missing title "+str(yaml_node))

            if "options" in yaml_node:
                print("modal node", yaml_node["id"],"definition has options defined in it. Note this will be ignored")

            fields = {}
            if "fields" in yaml_node:
                for yaml_field in yaml_node["fields"]:
                    if (not "label" in yaml_field) or (not "id" in yaml_field):
                        raise Exception("modal node \""+yaml_node["id"]+"\" has mis formed field" + yaml_field )
                    # note, temporarily using option class because it has all the parameters needed already
                    fields[yaml_field["id"]] = OptionInfo(yaml_field)
            return ModalInfo({**yaml_node, "fields":fields})

        elif "type" in yaml_node and yaml_node["type"] == "reply":
            if "next_node" in yaml_node and (not type(yaml_node["next_node"]) is str):
                self.nodes[yaml_node["next_node"]["id"]] = self.parse_node(yaml_node["next_node"])
                if yaml_node["next_node"]["id"] == yaml_node["id"]:
                    # edge case where the next node of this option can try to define the same node currently in the middle of being loaded. 
                    #       loops are allowed but redefining not. currently would get overwritten by parse node later
                    print("warning, bad format. reply node", yaml_node["id"],"next node is redefining node currently being parsed. will be overwritten once parsing is done")
                yaml_node["next_node"] = yaml_node["next_node"]["id"]
            return ReplyNodeInfo(yaml_node)
        else:
            # assuming if not labeled or otherwise labeled incorrectly, is a dialog. 
            if (not "prompt" in yaml_node):
                # currently requiring all dialog nodes need a prompt
                raise Exception("dialog node missing prompt: "+ str(yaml_node))

            if "fields" in yaml_node:
                print("dialog node definition has fields defined in it. Note this will be ignored")

            options = {}
            # ensure any options for this dialog are loaded correctly before saving dialog
            if "options" in yaml_node:
                for yaml_option in yaml_node["options"]:
                    loaded_option = self.load_option(yaml_option, yaml_node)
                    if loaded_option.id in options:
                        raise Exception("option \""+loaded_option.id+"\" already defined for dialog node \""+yaml_node["id"]+"\"")
                    options[yaml_option["id"]] = loaded_option
            return DialogInfo({**yaml_node, "options":options})

    def load_option(self, yaml_option, yaml_parent_dialog):
        ''' creates and returns OptionInfo object to hold option data. raises exceptions when data is missing and adds 
                any in-line definitions for nodes to the handler'''
        if (not "label" in yaml_option) or (not "id" in yaml_option):
            raise Exception("option missing label or id"+ str(yaml_option))

        if "next_node" in yaml_option and (not type(yaml_option["next_node"]) is str):
            # mext_node should be the id of next node. In line definitions have a dict there. need to be created and changed to id
            self.nodes[yaml_option["next_node"]["id"]] = self.parse_node(yaml_option["next_node"])
            if yaml_option["next_node"]["id"] == yaml_parent_dialog["id"]:
                # edge case where the next node of this option can try to define the same node currently in the middle of being loaded. 
                #       loops are allowed but redefining not. currently would get overwritten by parse node later
                print("warning, bad format. option",yaml_option["id"],"next node is redefining node currently being parsed. will be overwritten once parsing is done")
            yaml_option["next_node"] = yaml_option["next_node"]["id"]
        return OptionInfo(yaml_option)

    def load_file(self, file_name):
        '''load a yaml file with one or more yaml documents defining nodes into python objects. Those definitions are stored in self'''
        with open(file_name) as file:
            doc_dict = yaml.safe_load_all(file)
            for yaml_doc in doc_dict:
                for yaml_node in yaml_doc:
                    self.nodes[yaml_node["id"]] = self.parse_node(yaml_node)
        print("finished loading files", self.nodes)
    
    def final_validate():
        #TODO: function goes through all loaded dialog stuff to make sure it's valid. ie all items have required parems, 
        #       parems are right format, references point to regestered commands and dialogs, etc
        pass

    # this makes it eaiser, one spot to find all functions. and also good for security against bad configs
    def register_dialog_callback(self, func):
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
        print("doing command callback", f"command name  <{command_name}>", "node or option callback unkown")
        if command_name in self.callbacks:
            if inspect.iscoroutinefunction(self.callbacks[command_name]):
                await self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)
            else:
                self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)
    
    def print_detailed_saved_data(self):
        '''only for debugging purposes. prints out long form information about stored state'''
        indent = "   "
        if len(self.active_listeners) > 0:
            print(indent, "recorded nodes awaiting responses")
            for node_message_id, save in self.active_listeners.items():
                if node_message_id == "modals":
                    for modal_message_id, modal_data in save.items():
                        print(indent, indent, f"msg id: <{modal_message_id}>", f"node id<{modal_data['modal'].node_name}>", "type: modal", f"finished? <{modal_data['modal'].is_finished()}>")
                else:
                    view_info = ("view finished? <"+str(save["view"].is_finished()) + "> object memory address <" + str(id(save["view"])) + "> view message id <"+str(save["view"].message.id) +">" if "view" in save else "")
                    print(indent, indent, f"msg id <{node_message_id}>", f"node id <{save['node_name']}>", view_info, f"all keys {save.keys()}")
        else:
            print(indent, "no recorded nodes awaiting responses")
        
        if len(self.flow_progress) > 0:
            print(indent, "recorded save progress")
            for k,v in self.flow_progress.items():
                reply_submit_info = ",".join(["{node id "+ node_id + "content "+ str(submission.content)+"}" for node_id,submission in v["reply_submits"].items()]) if "reply_submits" in v else ""
                modal_submit_info = ",".join(["{node id "+ node_id + "content "+ str(submission)+"}" for node_id,submission in v["modal_submits"].items()]) if "modal_submits" in v else ""

                print(indent, indent, f"user id <{k[0]}>", f"node id <{k[1]}>", f"recorded type <{v['type']}>", f"flag <{v['flag']}>" if "flag" in v else "", f"previous nodes <{v['prev_nodes']}>", f"all keys <{v.keys()}>")
                if "reply_submits" in v:
                    print(indent, indent, indent, "reply submit values")
                    print(indent, indent, indent, reply_submit_info)
                if "modal_submits" in v:
                    print(indent, indent, indent, "modal submit values")
                    print(indent, indent, indent, modal_submit_info)
        else:
            print(indent, "no recorded flow progress")

    def print_compact_saved_data(self):
        '''only for debugging purposes. prints out a more compact form information about stored state'''
        open_dialog_info = ", ".join(["{id:"+str(message_id)+ " dialog:"+save["node_name"]+"}" for message_id, save in self.active_listeners.items() if message_id != "modals"])
        print("non modal nodes awaiting responses", open_dialog_info)
        open_dialog_info = ", ".join(["{id:"+str(message_id)+ " dialog:"+save["node_name"]+"}" for message_id, save in self.active_listeners["modals"].items()])
        print("modal nodes awaiting responses (this one is a bit bugged)", open_dialog_info)
        print("open flow progress", self.flow_progress.keys())


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
        print("dialog handler start of send dialog", f"dialog id: <{dialog_id}>", f"context-giving object type: <{passed_in_type}>",
                f"memory address of context-giving object: <{id(interaction_msg_or_context)}>", 
                "interaction id "+str(interaction_msg_or_context.id) if passed_in_type == "interaction" else "")
        #TODO: add option to add data to dialog objects, data only saved with the message, not passed into the saved progress
        dialog = self.nodes[dialog_id]
        send_method = interaction_send_message_wrapper(interaction_msg_or_context) \
                        if passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        #TODO: handle edge cases of 0, 1, > number of button slots options
        if len(dialog.options) > 0:
            view = DialogView(self, dialog_id)
            dialog_message = await send_method(content=dialog.prompt, view=view, **msg_options)
            view.mark_message(dialog_message)
            self.active_listeners[dialog_message.id] = {"node_name": dialog_id, "view":view, "message":dialog_message}
            print("dialog has multiple options so creating view and sending message. added info:", 
                    f"message id: <{self.active_listeners[dialog_message.id]['message'].id}>", 
                    f"dialog id: <{self.active_listeners[dialog_message.id]['node_name']}>", 
                    f"memory address of view: <{id(self.active_listeners[dialog_message.id]['view'])}>", 
                    f"children memory addresses: <{str([id(child) for child in view.children])}>")
        else:
            # not clear how to handle only one option listed 
            dialog_message = await send_method(content=dialog.prompt, **msg_options)
            self.active_listeners[dialog_message.id] = {"node_name": dialog_id, "view":None, "message":dialog_message}
            print("dialog has zero options, sending message only", 
                    f"message id <{self.active_listeners[dialog_message.id]['message'].id}>", 
                    f"dialog id <{self.active_listeners[dialog_message.id]['node_name']}>")

        # do the command for the dialog
        if dialog.command:
            await self.execute_command_callback(dialog.command, open_dialog=self.active_listeners[dialog_message.id] if dialog_message.id in self.active_listeners else {})

        # if there are fewer than 1, then we really aren't waiting for a choice to be made so dialog not really open anymore.
        #TODO: maybe don't even do this dance of adding and removing for the callback if there aren't any options? why would this be needed?
        if len(dialog.options) < 1:
            await self.close_node(dialog_message.id, "dialog")
        print("dialog handler end of send dialog")
        return dialog_message

    # thinking needed a separate method for this but seems still simple one line thing so it's still in handle interaction
    async def send_modal(self, node_id, interaction):
        print("dialog handler start of send modal", 
                f"node id: <{node_id}>", 
                f"interaction id: <{interaction.id}>",
                f"message id: <{interaction.message.id}>")
        modal = DialogModal(self, node_id)

        await interaction.response.send_modal(modal)

        if "modals" not in self.active_listeners:
            # message id for button interactions seem to be message the button is on, which can conflict with recorded info for dialog nodes
            # so I guess seperate section for modals?
            self.active_listeners["modals"] = {}
        if interaction.message.id in self.active_listeners["modals"]:
            #TODO: Wnat to test this branch more
            # dialogs are always new message so don't need this check. modals can be triggered by a message that stays and thus be re-added
            await self.close_node(interaction.message.id, "modal")
            print("send modal found modal already existed for this message id", interaction.message.id, "it is now replaced")
        self.active_listeners["modals"][interaction.message.id] = {"node_name":node_id, "modal":modal, "message":interaction.message}
        print("end of send modal",
                f"node id: <{node_id}>", 
                f"interaction id: <{interaction.id}>",
                f"memory address of modal", id(modal))

    async def send_reply_node(self, node_id, interaction_msg_or_context, passed_in_type, msg_opts={}):
        print("dialog handler start of sending reply node", f" node id: <{node_id}>", 
                f"memory address of context-giving object <{id(interaction_msg_or_context)}>",
                f"type of context-giving object: <{passed_in_type}>")

        reply_node_info = self.nodes[node_id]
        msg_contents = reply_node_info.prompt if reply_node_info.prompt else "Please type response in chat"
        send_method = interaction_send_message_wrapper(interaction_msg_or_context) if \
                        passed_in_type == "interaction" else interaction_msg_or_context.channel.send
        prompt_message = await send_method(content=msg_contents, **msg_opts)
        #TODO: fancier filters
        #TODO: need a timeout for waiting for replies?
        #TODO: automatic add a cancel button? or allow options on the node?
        self.active_listeners[prompt_message.id] = {"node_name": node_id, "message":prompt_message, "filters":{}}
        if passed_in_type == "interaction":
            self.active_listeners[prompt_message.id]["filters"].update({"channel":interaction_msg_or_context.channel.id, "user":interaction_msg_or_context.user.id})
        else:
            self.active_listeners[prompt_message.id]["filters"].update({"channel":interaction_msg_or_context.channel.id, "user":interaction_msg_or_context.author.id})
        print("end of sending reply node", 
                f"node id <{node_id}>", 
                f"message id <{prompt_message.id}>", 
                f"recorded filters for this node: {self.active_listeners[prompt_message.id]['filters']}")
        self.print_detailed_saved_data()

    async def do_node_action(self, node_name, interaction_msg_or_context, msg_opts = {}, passed_in_type = None):
        '''entry point for doing actions related to node itself'''
        print("handler node action beginning",
                f"node id {node_name}")
        if not passed_in_type:
            # denote whether we were given an interaction obj to respond to and for context, context obj, or message obj for chaining.
            # having this passed around as well so this doesn't have to be recalculated
            passed_in_type = "interaction" if issubclass(type(interaction_msg_or_context), Interaction) else ("message" if isinstance(interaction_msg_or_context, discord.Message) else "context")
        node_info = self.nodes[node_name]

        if node_info.type == "dialog":
            await self.send_dialog(node_name, interaction_msg_or_context, passed_in_type, msg_opts)
        elif node_info.type == "modal":
            if not issubclass(type(interaction_msg_or_context), Interaction):
                raise Exception("Invalid state. dialog handler next node is a modal, was passed a context when it must be an interaction")
            await self.send_modal(node_name, interaction_msg_or_context)
        elif node_info.type == "reply":
            await self.send_reply_node(node_name, interaction_msg_or_context, passed_in_type)
        print("'end of node action")

    '''################################################################################################
    #
    # RESPONDING TO CHOICES AND CHAINING NODES
    #
    ################################################################################################'''

    async def handle_interaction(self, interaction):
        ''' handle clicks and interactions with message components on messages that are tracked as open dialogs. handles identifying which action it is, 
        callback for that interaction, and sending the next dialog in the flow'''
        print("dialog handler start handling interaction", 
                f"interaction id: <{interaction.id}>", 
                f"message id: <{interaction.message.id}>", 
                f"raw data in: <{interaction.data}>", 
                f"interaction extras <{interaction.extras}>")

        # grab information needed to handle interaction on any supported node type
        node_info = self.nodes[interaction.extras["node_name"]]
        saved_progress = None
        if (interaction.user.id, node_info.id) in self.flow_progress:
            saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
        next_node_name = None
        end_progress_transfer = None
        
        if interaction.type == InteractionType.modal_submit:
            print("handle interaction modal submit branch")

            if not (interaction.user.id, node_info.id) in self.flow_progress:
                self.flow_progress[(interaction.user.id, node_info.id)] = {"node_name": node_info.id, "user":interaction.user, "prev_nodes":set()}
                saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
            
            self.flow_progress[(interaction.user.id, node_info.id)]["type"] = "modal"
            if "modal_submits" not in self.flow_progress[(interaction.user.id, node_info.id)]:
                self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"] = {}
            #TODO: saving modal submit information needs a bit of format finetuning
            self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"][node_info.id] = interaction.data["components"]
            print("dialog handler updated saved progres with modal submitted info", self.flow_progress[(interaction.user.id, node_info.id)]["modal_submits"])

            if node_info.submit_callback and node_info.submit_callback in self.callbacks:
                await self.execute_command_callback(node_info.submit_callback, 
                        open_dialog=None, 
                        progress=saved_progress, 
                        interaction=interaction)
            next_node_name = node_info.next_node
            end_progress_transfer = node_info.end
            print("dialog hanlder finished modal submit branch",
                    f"node id: <{node_info.id}>",
                    f"interaction id: <{interaction.id}>",
                    f"is there saved progress: <{'yes' if saved_progress else 'no'}>")
        else:
            if not interaction.message.id in self.active_listeners:
                return
            # grabbing dialog specific information
            chosen_option = node_info.options[interaction.data["custom_id"]]
            print("found interaction on", f"message <{interaction.message.id}>", "is for dialog", f"<{node_info.id}>", f"chosen option: <{chosen_option}>", f"next node info <{chosen_option.next_node}>")
            print("cont.", f"memory address of view for message<{id(self.active_listeners[interaction.message.id]['view'])}>")

            # update saved data because any flags and data from an option applies when that option is chosen
            if chosen_option.data or chosen_option.flag:
                # might not be any preexisting saved data, create it
                if not (interaction.user.id, node_info.id) in self.flow_progress:
                    print("save data added for", (interaction.user.id, node_info.id), "because the option adds data")
                    self.flow_progress[(interaction.user.id, node_info.id)] = {"node_name": node_info.id, "user":interaction.user, "prev_nodes":set()}
                    saved_progress = self.flow_progress[(interaction.user.id, node_info.id)]
                else:
                    print("handle interaction found save data for", (interaction.user.id, node_info.id))
                self.flow_progress[(interaction.user.id, node_info.id)]["type"] = "dialog"
                if chosen_option.data:
                    if not "data" in saved_progress:
                        saved_progress["data"] = {}
                    saved_progress["data"].update(chosen_option.data)
                if chosen_option.flag:
                    saved_progress["flag"] = chosen_option.flag
            
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
        print("end handle interaction",
                f"node id <{node_info.id}>",
                f"message id <{interaction.message.id}>")
                        

    async def handle_chaining(self, curr_node, next_node_id, end_progress_transfer, interaction_msg_or_context, passed_in_type=None):
        print("started handling chaining from",curr_node.id, "to next node", next_node_id, f"end progres transfer? <{end_progress_transfer}>")
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

        print('handling chaining', f"memory address of context-giving object <{id(interaction_msg_or_context)}>",
                f"type of context-giving object: <{passed_in_type}>",
                f"found saved data? {'yes' if saved_progress else 'no'}",
                f"interaction id: <{interaction_msg_or_context.id if passed_in_type == 'interaction' else ''}>")

        # print("handling chaining, finding basic data","user id", user.id,"curr_node", curr_node.id, "saved progress", saved_progress.keys() if saved_progress else "NONE", "all saved flow", self.flow_progress.keys())
        if next_node_id and not (next_node_id in self.nodes):
            print(f"warning, tyring to chain from {curr_node.id} to {next_node_id} but next node not registered. ignoring and dropping for now, double check definitions.")

        if next_node_id in self.nodes:
            # next node is registered properly, means need to go to next node and deal with save data
            next_node = self.nodes[next_node_id]
            print("handling chaining, next node found.", f"type: <{next_node.type}>")
            if next_node.type == "dialog":
                # TODO: assuming when need to progress is getting messy.
                #       some dialogs branch and need to transfer data, others do not. the guessing so far supports a help 
                #       button that prints out extra message, does not affect save state, and execute continues from message with help button
                if curr_node.type == "dialog" and saved_progress and curr_node_message.id in self.active_listeners and len(next_node.options) > 0:
                    await self.clean_clickables(self.active_listeners[curr_node_message.id])
                await self.do_node_action(next_node_id, interaction_msg_or_context)
                # print("dialog handler end of handling interaction internal", interaction)
                if saved_progress:
                    if not end_progress_transfer and len(next_node.options) > 0:
                        print("next node is dialog, and save data needs to be progressed")
                        self.flow_progress[(user.id, next_node_id)] = {**self.flow_progress[(user.id, curr_node.id)], "type":"dialog"}
                        self.flow_progress[(user.id, next_node_id)]["prev_nodes"].add(curr_node.id)
                        del self.flow_progress[(user.id, curr_node.id)]
                    if end_progress_transfer:
                        del self.flow_progress[(user.id, curr_node.id)]
            elif next_node.type == "modal" or next_node.type == "reply":
                if curr_node.type == "dialog" and saved_progress and curr_node_message.id in self.active_listeners:
                    await self.clean_clickables(self.active_listeners[curr_node_message.id])
                await self.do_node_action(next_node_id, interaction_msg_or_context)
                if saved_progress:
                    if not end_progress_transfer:
                        self.flow_progress[(user.id, next_node_id)] = self.flow_progress[(user.id, curr_node.id)]
                        self.flow_progress[(user.id, next_node_id)]["type"] = next_node.type
                        self.flow_progress[(user.id, next_node_id)]["prev_nodes"].add(curr_node.id)
                    del self.flow_progress[(user.id, curr_node.id)]
        else:
            # no next node, end of line so clean up
            print("handling chaining, no next node.", f"current node id: <{curr_node.id}>")
            if passed_in_type == "interaction":
                await interaction_msg_or_context.response.send_message(content="interaction completed", ephemeral=True)
            if saved_progress:
                    if curr_node.type == "dialog" and curr_node_message.id in self.active_listeners:
                        await self.clean_clickables(self.active_listeners[curr_node_message.id])
                    del self.flow_progress[(user.id, curr_node.id)]

        # final net for catching interactions to make it less confusing for user
        if passed_in_type == "interaction" and not interaction_msg_or_context.response.is_done():
            print("dialog handler handle chaining reached special interaction complete check", 
                    f"node id: <{curr_node.id}>", 
                    f"interaction id: <{interaction_msg_or_context.id}>")
            await interaction_msg_or_context.response.send_message(content="interaction completed", ephemeral=True)
        print("dialog handler after chaining saved progress")
        self.print_detailed_saved_data()

    async def on_message(self, message: discord.Message):
        print("start on message call in dialog handler, starting filtering", f"message id <{message.id}>", f"contents <{message.content}>")
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
            print("message id", message.id, "is not reply to any reply nodes")
            return

        # handle all actions about saving info and moving onto next step
        node_info = self.nodes[found_node_id]
        print("on message found valid in-chat reply", f"message id: <{message.id}>", f"node id: <{found_node_id}>")

        # assuming information sent via reply is like a form submit and should immediately be saved
        if not (message.author.id, node_info.id) in self.flow_progress:
            self.flow_progress[(message.author.id, node_info.id)] = {"node_name": node_info.id, "user":message.author, "prev_nodes":set()}
        saved_progress = self.flow_progress[(message.author.id, node_info.id)]
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

        print("end of handler on message handling in-channel reply message")

    async def on_interaction(self, interaction):
        '''custom system for filtering all relevant interactions. needs to be added to bot as listener.
        Currently used as a workaround to how Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id'''
        if interaction.type == InteractionType.modal_submit:
            if not "modals" in self.active_listeners:
                return
            if not interaction.message.id in self.active_listeners["modals"]:
                return 
            await self.active_listeners["modals"][interaction.message.id]["modal"].do_submit(interaction)
        if interaction.type == InteractionType.component:
            if not interaction.message.id in self.active_listeners:
                return
            listener = self.active_listeners[interaction.message.id]
            if not "view" in listener or not listener["view"]:
                return
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

    async def close_dialog(self, message_id):
        '''depreacted, use close_node. removes interaction buttons from message to prevent further interactions starting from this dialog message'''
        #TODO: error edgecase handling
        #       View already expired/not there
        if message_id in self.active_listeners:
            data = self.active_listeners[message_id]
            print("Dialog Handler close dialog internal", "message", message_id, "for dialog", data["node_name"])
            view = data["view"]
            view.clear_items()
            await data["message"].edit(view=view)
            del self.active_listeners[message_id]

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
                    view.clear_items()
                    await node_data["message"].edit(view=view)
                del self.active_listeners[active_listner_key]
        elif node_type == "modal":
            if ["modals"] in self.active_listeners and active_listner_key in self.active_listeners["modals"]:
                del self.active_listeners["modals"][active_listner_key]
        elif node_type == "reply":
            node_data = self.active_listeners[active_listner_key]
            if not fulfilled:
                await node_data["message"].edit(content="responses are closed")
            del self.active_listeners[active_listner_key]
        print("end of close node on", 
                f"message id: <{ active_listner_key}>")

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
        print("Dialog view initialized", f"object memory address <{id(self)}>", f"node id <{node_name}>")

        dialog = self.dialog_handler.nodes[node_name]
        for op_id, option in dialog.options.items():
            self.add_item(DialogButton(self.dialog_handler, label=option.label, custom_id=option.id))

    def mark_message(self, message):
        self.message = message
    
    async def on_timeout(self):
        print("Dialog view on timeout callback", f"object memory address <{id(self)}>", f"message id <{self.message.id}>", f"node id <{self.node_name}>")
        await super().on_timeout()
        await self.dialog_handler.close_node(self.message.id, "dialog")

    async def stop(self):
        print("Dialog view stopped", f"object memory address <{id(self)}>", f"message id <{self.message.id}>", f"node id <{self.node_name}>")
        super().stop()
        await self.dialog_handler.close_node(self.message.id, "dialog")

    def __del__(self):
        print("dialog view", id(self), "has been destroyed")

class DialogButton(ui.Button):
    def __init__(self, handler, **kwargs):
        # print("dialogButton init internal", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler
        print("Dialog button initialized", f"object memory address >{id(self)}>")

    async def do_callback(self, interaction):
        '''renamed from default callback function. Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id, so a custom callback system is used. Workaround for now is
        for handler to find the right button to callback and rename function so regular system doesn't cause double calls on a single event'''
        print("Dialog button clicked", 
                f"interaction id <{interaction.id}>",
                f"message id <{interaction.message.id}>", 
                f"view object memory address <{id(self.view)}>",
                f"raw data in <{interaction.data}>"
                f"node id <{self.view.node_name}>")
        interaction.extras["node_name"] = self.view.node_name
        await self.dialog_handler.handle_interaction(interaction)

    def __del__(self):
        print("dialog button", id(self), "has been destroyed")

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
            self.add_item(ui.TextInput(label=field.label, custom_id = field.label))

    async def do_submit(self, interaction):
        '''renamed from default on_submit function. Discord.py 2.1.0 seems to keep finding the wrong button to callback when there
        are buttons from different active view objects with the same custom_id, so a custom callback system is used. Workaround for now is
        for handler to find the right button to callback and rename function so regular system doesn't cause double calls on a single event'''
        interaction.extras["node_name"] = self.node_name
        print("modal submitted", f"node id <{self.node_name}>", f"submitted data <{interaction.data}>", f"interaction message <{interaction.message.id}>")
        await self.dialog_handler.handle_interaction(interaction)

    async def on_timeout(self):
        # seems like default for modals is nevr time out?
        print("modal", self.node_name, "timed out")

async def submit_results(open_dialog=None, progress=None, interaction=None):
    #NOTE: VERY ROUGH RESULT MESSAGE JUST FOR PROOF OF CONCEPT THAT DATA WAS STORED. MUST BE EDITED ONCE FORMAT IS FINALIZED (yes its messy)
    await interaction.channel.send("questionairre received "+progress["modal_submits"]["questionairreModal"][0]["components"][0]["value"])