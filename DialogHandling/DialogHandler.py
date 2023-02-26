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
#TODO: implement save and load data about what's in progress
#       otherwise it currently leaves hanging buttons on previous messages that were sent before restart
#TODO: handle view timeouts better, save data isn't cleaned up, but is that needed?
#TODO: handle interaction needs to check in with active listeners and if that now needs to be deactivated 
#       and maybe custom limits like max number of reactors instead of built in view timeout
#TODO: finishing modal obj definitions
#TODO: Figure out what sorts of data get passed into callbacks
#       currently: dialog callbacks won't have progress or interaction ones
#       callbacks from interactions hve interaction, and progress if data has been added

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
        self.nodes["default_completed"] = Dialog({"name":"default_completed", "prompt":"completed"})

    def parse_node(self, yaml_node):
        #TODO: more edgecase and format guards for loading files
        if (not "name" in yaml_node):
            # basically all loaded items must have a name
            print("yaml object (dialog or modal definition) mis-formed. skipping")
            raise Exception("yaml object misformed")

        if yaml_node["name"] in self.nodes:
            raise Exception("redefinition of existing node")

        # yaml needs a type flag to specify what it is, default is dialog object
        if "type" in yaml_node and yaml_node["type"] == "modal":
            if (not "title" in yaml_node):
                # basically all modals must have a name
                print("modal mis-formed. skipping")
                raise Exception("modal misformed")

            fields = {}
            if "fields" in yaml_node:
                for yaml_field in yaml_node["fields"]:
                    if (not "label" in yaml_field) or (not "id" in yaml_field):
                        print("field for modal", yaml_node["name"], "mis-formed. skipping")
                        continue
                    # note, temporarily using option class because it has all the parameters needed already
                    fields[yaml_field["id"]] = Option(yaml_field)
            return ModalInfo({**yaml_node, "fields":fields})
        else:
            options = {}
            # ensure options for this dialog are loaded correctly before registering dialog
            if "options" in yaml_node:
                for yaml_option in yaml_node["options"]:
                    options[yaml_option["id"]] = self.load_option(yaml_option)
            # assuming if not labeled or otherwise labeled incorrectly, is a dialog. 
            return Dialog({**yaml_node, "options":options})

    def load_option(self, yaml_option):
        if (not "label" in yaml_option) or (not "id" in yaml_option):
            # print("option for dialog", yaml_node["name"], "mis-formed. skipping")
            raise Exception("option misformed")

        if "next_node" in yaml_option and (not type(yaml_option["next_node"]) is str):
            self.nodes[yaml_option["next_node"]["name"]] = self.parse_node(yaml_option["next_node"])
            yaml_option["next_node"] = yaml_option["next_node"]["name"]
        return Option(yaml_option)

    def load_file(self, file_name):
        '''load a yaml file with one or more yaml documents defining nodes into python objects'''
        with open(file_name) as file:
            doc_dict = yaml.safe_load_all(file)
            for yaml_doc in doc_dict:
                for yaml_node in yaml_doc:
                    self.nodes[yaml_node["name"]] = self.parse_node(yaml_node)
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
        children_info = ", ".join(["{ "+str(type(child))+" label:"+child.label+" custom id:"+child.custom_id+"}" for child in view.children])
        print("build clickables", "for dialog", dialog_name, "clickables", children_info)
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
            if inspect.iscoroutinefunction(self.callbacks[command_name]):
                await self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)
            else:
                self.callbacks[command_name](open_dialog=kwargs["open_dialog"], 
                        progress=kwargs["progress"] if "progress" in kwargs else None, 
                        interaction=kwargs["interaction"]if "interaction" in kwargs else None)

    # Likely not using in future. Also want to manage rest of sending and taking care of callbacks/data when sending new dialog so this doesn't cover enough
    # def register_open_dialog(self, message, dialog_name, view, data={}):
    #     self.message_status[message.id] = {**data, "dialog_name":dialog_name, "message":message, "view":view}
    
    #TODO: interaction response calls require a wrapper for this, is that a good solution? otherwise it works for responding to text and to interactions
    async def send_dialog(self, send_method, dialog_name, send_options={}):
        '''
        When you need to send a new message that contains dialog with options to choose. Handles sending, tracking, and dialog callbacks
        Parem
        -----
        send_method - coroutine
            reference to function to call to send a message. should already point to destination, and message and other options can be passed in.
            Must return the resulting message that was just sent, so if its an interaction response use the wrapper in this file
        '''
        #TODO: add option to add data to dialog objects, data only saved with the message, not passed into the saved progress
        dialog = self.nodes[dialog_name]
        #TODO: handle edge cases of 0, 1, > number of button slots options
        if len(dialog.options) > 0:
            view = DialogView(self, dialog_name)
            dialog_message = await send_method(content=dialog.prompt, view=view, **send_options)
            view.mark_message(dialog_message)
            self.active_listeners[dialog_message.id] = {"dialog_name": dialog_name, "view":view, "message":dialog_message}
        else:
            # not clear how to handle only one option listed 
            dialog_message = await send_method(content=dialog.prompt, **send_options)
            self.active_listeners[dialog_message.id] = {"dialog_name": dialog_name, "view":None, "message":dialog_message}

        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id, save in self.active_listeners.items()])
        print("dialog handler send dialog middle", "dialog message id", dialog_message.id, "dialog name", dialog_name, "is there a view", self.active_listeners[dialog_message.id]["view"], " all open dialogs", open_dialog_info)

        # do the command for the dialog
        if dialog.command:
            await self.execute_command_callback(dialog.command, open_dialog=self.active_listeners[dialog_message.id])

        # if there are fewer than 1, then we really aren't waiting for a choice to be made so dialog not really open anymore.
        #TODO: maybe don't even do this dance of adding and removing for the callback if there aren't any options? why would this be needed?
        if len(dialog.options) < 1:
            del self.active_listeners[dialog_message.id]
        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id, save in self.active_listeners.items()])
        print("dialog handler end of send dialog internal", "open dialog message ids", open_dialog_info)
        return dialog_message

    # thinking needed a separate method for this but seems still simple one line thing so it's still in handle interaction
    async def send_modal(self, node_name, interaction):
        pass

    async def do_node_action(self, node_name, interaction_or_context, msg_opts = {}):
        #TODO: this has a lot of spaghetti mess thoughts around format. very WIP
        node_info = self.nodes[node_name]
        if isinstance(node_info, Dialog):
            await self.send_dialog(
                    interaction_send_message_wrapper(interaction_or_context) 
                        if issubclass(interaction_or_context, Interaction) else interaction_or_context,
                    node_name, 
                    msg_opts)
        else:
            pass
        pass

    async def handle_interaction(self, interaction):
        ''' handle clicks and interactions with message components on messages that are tracked as open dialogs. handles identifying which action it is, 
        callback for that interaction, and sending the next dialog in the flow'''
        print("dialog handler start handling interaction", "interaction's message", interaction.message.id, "raw data in", interaction.data)
        open_dialog_info = ", ".join(["{id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id, save in self.active_listeners.items()])
        print("dialog handler start handling interaction saved progress", self.flow_progress.keys(), "open dialogs", open_dialog_info)
        print("dialog handler start handling interaction extras", interaction.extras)

        # grab information needed to handle interaction on any supported node type
        node_info = self.nodes[interaction.extras["node_name"]]
        saved_progress = None
        if (interaction.user.id, node_info.name) in self.flow_progress:
            saved_progress = self.flow_progress[(interaction.user.id, node_info.name)]
        next_node_name = None
        end_progress_transfer = None
        
        if interaction.type == InteractionType.modal_submit:
            print("dialog handler modal submit branch")

            if not (interaction.user.id, node_info.name) in self.flow_progress:
                self.flow_progress[(interaction.user.id, node_info.name)] = {"node_name": node_info.name, "user":interaction.user, "type": "modal"}
                saved_progress = self.flow_progress[(interaction.user.id, node_info.name)]
            
            self.flow_progress[(interaction.user.id, node_info.name)]["modal_submits"] = {}
            #TODO: saving modal submit information needs a bit of format finetuning
            self.flow_progress[(interaction.user.id, node_info.name)]["modal_submits"][node_info.name] = interaction.data["components"]
            print("dialog handler updated saved progres with modal submitted info", self.flow_progress[(interaction.user.id, node_info.name)]["modal_submits"])

            if node_info.submit_callback and node_info.submit_callback in self.callbacks:
                await self.execute_command_callback(node_info.submit_callback, 
                        open_dialog=None, 
                        progress=saved_progress, 
                        interaction=interaction)
            next_node_name = node_info.next_node
            end_progress_transfer = node_info.end
            print("dialog hanlder finished modal submit branch")
        else:
            if not interaction.message.id in self.active_listeners:
                return

            # grabbing dialog specific information
            chosen_option = node_info.options[interaction.data["custom_id"]]
            print("found interaction on", "message", interaction.message.id, "is for dialog", node_info.name, "chosen option:", chosen_option, "dialog info", chosen_option.next_node)

            # update saved data because any flags and data from an option applies when that option is chosen
            if chosen_option.data or chosen_option.flag:
                # might not be any preexisting saved data, create it
                if not (interaction.user.id, node_info.name) in self.flow_progress:
                    print("save data added for", (interaction.user.id, node_info.name), "because the option adds data")
                    self.flow_progress[(interaction.user.id, node_info.name)] = {"node_name": node_info.name, "user":interaction.user, "type": "dialog"}
                    saved_progress = self.flow_progress[(interaction.user.id, node_info.name)]
                else:
                    print("handle interaction found save data for", (interaction.user.id, node_info.name))

                if chosen_option.data:
                    if not "data" in saved_progress:
                        saved_progress["data"] = {}
                    saved_progress["data"].update(chosen_option.data)
                if chosen_option.flag:
                    saved_progress["flag"] = chosen_option.flag
            print("dialog handler handle interaction saved progress before callback", "this interaction progress", self.flow_progress[(interaction.user.id, node_info.name)].keys() if (interaction.user.id, node_info.name) in self.flow_progress else "NONE" , "all keys", self.flow_progress.keys())
            
            # handling callback stage
            if chosen_option.command:
                await self.execute_command_callback(chosen_option.command, 
                        open_dialog=self.active_listeners[interaction.message.id], 
                        progress=saved_progress, 
                        interaction=interaction)
                # await interaction.response.send_modal(Questionnaire())
            
            next_node_name = chosen_option.next_node
            end_progress_transfer = chosen_option.end
                        
        # handling interaction response and wrapping up stage
        #TODO: implementing different ways of finishing handling interaction. can be editing message, sending another message, or sending a modal
        #       would like to specify in yaml if edit or send new message to finish option, modals have been mostly implemented
        #TODO: better directing flow so that this can borrow a dialog from another dialog flow and stay on this one without needing to define a copy 
        #       of an existing dialog just so that we can go to a different dialog
        if next_node_name in self.nodes:
            next_node = self.nodes[next_node_name]
            if isinstance(next_node, Dialog):
                # TODO: assuming when need to progress is getting messy.
                #       some dialogs branch and need to transfer data, others do not. the guessing so far supports a help 
                #       button that prints out extra message, does not affect save state, and execute continues from message with help button
                must_advance_progress = not end_progress_transfer and len(next_node.options) > 0
                if saved_progress and interaction.message.id in self.active_listeners and len(self.nodes[next_node_name].options) > 0:
                    await self.clean_clickables(self.active_listeners[interaction.message.id])
                next_message = await self.send_dialog(interaction_send_message_wrapper(interaction), next_node_name)
                # print("dialog handler end of handling interaction internal", interaction)
                if saved_progress:
                    if must_advance_progress:
                        self.flow_progress[(interaction.user.id, next_node_name)] = {**self.flow_progress[(interaction.user.id, node_info.name)], "type":"dialog"}
                        del self.flow_progress[(interaction.user.id, node_info.name)]
            elif isinstance(next_node, ModalInfo):
                await interaction.response.send_modal(DialogModal(self, next_node_name))
                if saved_progress:
                    if not end_progress_transfer:
                        self.flow_progress[(interaction.user.id, next_node_name)] = self.flow_progress[(interaction.user.id,node_info.name)]
                        self.flow_progress[(interaction.user.id, next_node_name)]["type"] = "modal"
                    del self.flow_progress[(interaction.user.id,node_info.name)]
        else:
            # no next node, end of line so clean up
            await interaction.response.send_message(content="interaction completed", ephemeral=True)
            if saved_progress:
                if interaction.message.id in self.active_listeners:
                    await self.clean_clickables(self.active_listeners[interaction.message.id])
                del self.flow_progress[(interaction.user.id, node_info.name)]
        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id, save in self.active_listeners.items()])
        print("dialog handler end of handling interaction internal", "open dialogs", open_dialog_info, "saved progress", self.flow_progress.keys())

        # final net for catching
        if not interaction.response.is_done():
            print("dialog handler handle interaction final net somehow reached")
            await interaction.response.send_message(content="interaction completed", ephemeral=True)

    async def clean_clickables(self, open_dialog=None, progress=None, interaction=None):
        # print("clean clickables, passed in dialog", open_dialog)
        view = open_dialog["view"]
        # view.clear_items()
        await view.stop()
        # await data["message"].edit(view=view)
        # del self.message_status[data["message"].id]

    async def close_dialog(self, message_id):
        '''removes interaction buttons from message to prevent further interactions starting from this dialog message'''
        #TODO: error edgecase handling
        #       View already expired/not there
        if message_id in self.active_listeners:
            data = self.active_listeners[message_id]
            print("Dialog Handler close dialog internal", "message", message_id, "for dialog", data["dialog_name"])
            view = data["view"]
            view.clear_items()
            await data["message"].edit(view=view)
            del self.active_listeners[message_id]

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

        dialog = self.dialog_handler.nodes[node_name]
        for op_id, option in dialog.options.items():
            self.add_item(DialogButton(self.dialog_handler, label=option.label, custom_id=option.id))

    def mark_message(self, message):
        self.message = message
    
    async def on_timeout(self):
        print("Dialog view on timeout callback internal")
        await super().on_timeout()
        await self.dialog_handler.close_dialog(self.message.id)

    async def stop(self):
        print("Dialog view stop internal")
        super().stop()
        await self.dialog_handler.close_dialog(self.message.id)

class DialogButton(ui.Button):

    def __init__(self, handler, **kwargs):
        # print("dialogButton init internal", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler

    async def callback(self, interaction):
        print("Dialog button clicked", "message id", interaction.message.id, "raw data in", interaction.data)
        interaction.extras["node_name"] = self.view.node_name
        await self.dialog_handler.handle_interaction(interaction)

class DialogSelect(ui.Select):

    def __init__(self, handler, **kwargs):
        print("DialogSelect init internal", kwargs)
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

    async def on_submit(self, interaction):
        interaction.extras["node_name"] = self.node_name
        print("modal", self.node_name, "submit callback", interaction.data,"interaction type", interaction.type, "interaction message", interaction.message)
        await self.dialog_handler.handle_interaction(interaction)

    async def on_timeout(self):
        # seems like default for modals is nevr time out?
        print("modal", self.node_name, "timed out")

async def submit_results(open_dialog=None, progress=None, interaction=None):
    #NOTE: VERY ROUGH RESULT MESSAGE JUST FOR PROOF OF CONCEPT THAT DATA WAS STORED. MUST BE EDITED ONCE FORMAT IS FINALIZED (yes its messy)
    await interaction.channel.send("questionairre received"+progress["modal_submits"]["questionairreModal"][0]["components"][0]["value"])


#testing pop up modals. copied from docs. this one allows clicker to input information. has to be done in response to interactions
class Questionnaire(ui.Modal, title='Questionnaire Response'):
    name = ui.TextInput(label='Name')
    answer = ui.TextInput(label='Potato', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Thanks for your response, {self.name}!', ephemeral=True)