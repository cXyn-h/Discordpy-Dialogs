import yaml
import inspect
import discord
from discord import ui
from DialogHandling.DialogObjects import Dialog, Option

# WIP alpha version, will have tons of logging printout and unfinished areas.

#TODO: variable content of message: grab at run not from file
#TODO: testing flags and passing info from dialog to next in chain, and does this support needs
#TODO: support different ways to show options to select from?
#       support dropdown selection menus elements
#       option to not send as interactable buttons/selectors
#TODO: support modals
#TODO: implement save and load data about what's in progress
#       otherwise leave hanging buttons on previous messages

class DialogHandler():
    # passing in dialogs and callbacks if you want them shared between instances. not tested yet
    def __init__(self, dialogs = {}, callbacks = {}) -> None:
        self.dialogs = dialogs
        self.callbacks = callbacks
        #TODO: these probably need something that enforces certain structure to anything put inside
        self.interactable_messages = {}
        self.dialog_progress = {}
        # some default available items
        self.register_dialog_callback(self.clean_clickables)
        # this dialog might not be used in future
        self.dialogs["default_completed"] = Dialog({"name":"default_completed", "prompt":"completed"})

    def load_file(self, file_name):
        '''load a yaml file defining dialogs into python objects'''
        with open(file_name) as file:
            #TODO: change to load all. and a for each document
            dialog_dict = yaml.safe_load(file)
            #TODO: also having a list of dialogs on top layer has weird?different? formatting. check this and assumption that it all has to be dialogs at top level
            for dialog in dialog_dict:
                if (not "name" in dialog):
                    # basically all dialogs must have a name
                    print("dialog mis-formed. skipping")
                    continue

                options = {}
                # ensure options for this dialog are loaded correctly before registering dialog
                if "options" in dialog:
                    for option in dialog["options"]:
                        if (not "label" in option) or (not "id" in option):
                            print("option for dialog", dialog["name"], "mis-formed. skipping")
                            continue
                         # TODO: maybe have different option objects? will need to see where it goes
                        if "dialog" in option and (not type(option["dialog"]) is str):
                            # means in line definition of a dialog. register it and create option object so it only has the name
                            self.dialogs[option["dialog"]["name"]] = Dialog(option["dialog"])
                            options[option["id"]] = Option({**option, "dialog":option["dialog"]["name"]})
                        else:
                            options[option["id"]] = Option(option)

                self.dialogs[dialog["name"]] = Dialog({**dialog, "options":options})
    
    def final_validate():
        #TODO: function goes through all loaded dialog stuff to make sure it's valid. ie all items have required parems, 
        #       parems are right format, references point to regestered commands and dialogs, etc
        pass

    # this makes it eaiser, one spot to find all functions. and also good for security against bad configs
    def register_dialog_callback(self, func):
        #TODO: check not register function and how to make callbacks unmodifiable/inaccessible from outside?
        self.callbacks[func.__name__] = func

    def build_clickables(self, dialog_name):
        ''' create the object handling the interactable buttons you can click '''
        dialog = self.dialogs[dialog_name]
        view = DialogView(self)
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

    async def execute_command_callback(self, command_name, **kwargs):
        #TODO: still WIP on what exactly gets passed around and how. 
        #   currently: dialog callbacks won't have progress or interaction ones
        #       callbacks from interactions hve interaction, and progress if data has been added
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
    #     self.interactable_messages[message.id] = {**data, "dialog_name":dialog_name, "message":message, "view":view}
    
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
        dialog = self.dialogs[dialog_name]
        #TODO: handle edge cases of 0, 1, > number of button slots options
        if len(dialog.options) > 0:
            #TODO: if only showing interactables when more than one option gotta handle that option now?
            view = self.build_clickables(dialog_name)
            dialog_message = await send_method(content=dialog.prompt, view=view, **send_options)
            view.mark_message(dialog_message)
            self.interactable_messages[dialog_message.id] = {"dialog_name": dialog_name, "view":view, "message":dialog_message}
        else:
            # not clear how to handle only one option listed 
            dialog_message = await send_method(content=dialog.prompt, **send_options)
            self.interactable_messages[dialog_message.id] = {"dialog_name": dialog_name, "view":None, "message":dialog_message}

        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id,save in self.interactable_messages.items()])
        print("dialog handler send dialog middle","dialog message id", dialog_message.id, "dialog name", dialog_name, "is there a view", self.interactable_messages[dialog_message.id]["view"], " all open dialogs", open_dialog_info)

        # do the command for the dialog
        if dialog.command:
            await self.execute_command_callback(dialog.command, open_dialog=self.interactable_messages[dialog_message.id])

        # if there are fewer than 1, then we really aren't waiting for a choice to be made so dialog not really open anymore.
        # TODO: might need edits to handle modals
        #TODO: maybe don't even do this dance of adding and removing for the callback if there aren't any options? why would this be needed?
        if len(dialog.options) < 1:
            del self.interactable_messages[dialog_message.id]
        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id,save in self.interactable_messages.items()])
        print("dialog handler end of send dialog internal","open dialog message ids", open_dialog_info)
        return dialog_message

    #TODO: progress saving part needs some editing to accomodate help button that prints out extra message, does not affect save state, and execute continues from message with help button
    #       current implementation assumes all button clicks will move state forward, and that is chosen path can't go back and choose another
    async def handle_interaction(self, interaction):
        ''' handle clicks and interactions with message components on messages that are tracked as open dialogs. handles identifying which action it is,
        callback for that interaction, and sending the next dialog in the flow'''
        print("dialog handler start handling interaction", "message", interaction.message.id, "raw data in", interaction.data)
        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id,save in self.interactable_messages.items()])
        print("dialog handler start handling interaction saved progress", self.dialog_progress.keys(), "open dialogs", open_dialog_info)
        if not interaction.message.id in self.interactable_messages:
            return

        # grabbing information stage
        dialog = self.dialogs[self.interactable_messages[interaction.message.id]["dialog_name"]]
        chosen_option = dialog.options[interaction.data["custom_id"]]
        print("found interaction on","message", interaction.message.id, "is for dialog", dialog.name, "chosen option:", chosen_option,"is there a flag?", chosen_option.flag)

        # find better spot for this laterrrrr
        # if interaction.data["component_type"] == discord.ComponentType.select:

        # first stage of dialog progress updates (needed for callback)
        saved_progress = None
        if (interaction.user.id, dialog.name) in self.dialog_progress or chosen_option.data or chosen_option.flag:
            # check if there already is saved data for the option adds that data so it now needs to exist
            if not (interaction.user.id, dialog.name) in self.dialog_progress:
                print("save data added for", (interaction.user.id, dialog.name), "because the option adds data")
                self.dialog_progress[(interaction.user.id, dialog.name)] = {"dialog_name": dialog.name, "user":interaction.user}
            else:
                print("handle interaction found save data for", (interaction.user.id, dialog.name))
            # grab save data for refernece later, and update with the new data from this option. if future options also define these, this gets overwritten
            saved_progress = self.dialog_progress[(interaction.user.id, dialog.name)]
            if chosen_option.data:
                saved_progress.update({**chosen_option.data})
            if chosen_option.flag:
                saved_progress["flag"] = chosen_option.flag
        print("dialog handler handle interaction saved progress before callback", "this interaction progress", self.dialog_progress[(interaction.user.id, dialog.name)].keys() if (interaction.user.id, dialog.name) in self.dialog_progress else "NONE" , "all keys", self.dialog_progress.keys())
        
        # handling callback stage
        if chosen_option.command:
            await self.execute_command_callback(chosen_option.command, 
                    open_dialog=self.interactable_messages[interaction.message.id], 
                    progress=saved_progress,
                    interaction=interaction)
            # await interaction.response.send_modal(Questionnaire())
        
        # handling interaction response and wrapping up stage
        #TODO: implementing different ways of finishing handling interaction. can be editing message, sending another message, or sending a modal
        #       so far just have it always send a message, either dialog or ephemeral indicator so it doesn't say "interaction failed" all the time
        #       would like to have this as something the yaml for each option can specify
        #TODO: better directing flow so that this can borrow a dialog from another dialog flow and stay on this one without needing to define a copy 
        #       of an existing dialog just so that we can go to a different dialog
        if chosen_option.dialog and chosen_option.dialog in self.dialogs:
            must_advance_progress = not chosen_option.end and len(self.dialogs[chosen_option.dialog].options) > 0
            if saved_progress and interaction.message.id in self.interactable_messages and len(self.dialogs[chosen_option.dialog].options) > 0:
                await self.clean_clickables(self.interactable_messages[interaction.message.id])
            next_message = await self.send_dialog(interaction_send_message_wrapper(interaction), chosen_option.dialog)
            # print("dialog handler end of handling interaction internal", interaction)
            if saved_progress:
                if must_advance_progress:
                    self.dialog_progress[(interaction.user.id, chosen_option.dialog)] = self.dialog_progress[(interaction.user.id, dialog.name)]
                    del self.dialog_progress[(interaction.user.id, dialog.name)]             
        else:
            await interaction.response.send_message(content="interaction completed", ephemeral=True)

        if saved_progress and chosen_option.end:
            if interaction.message.id in self.interactable_messages:
                await self.clean_clickables(self.interactable_messages[interaction.message.id])
            del self.dialog_progress[(interaction.user.id, dialog.name)]
            

        open_dialog_info = ", ".join(["{ id:"+str(message_id)+ " dialog:"+save["dialog_name"]+"}" for message_id,save in self.interactable_messages.items()])
        print("dialog handler end of handling interaction internal","open dialogs", open_dialog_info, "saved progress", self.dialog_progress.keys())

    async def clean_clickables(self, open_dialog=None, progress=None, interaction=None):
        # print("clean clickables, passed in dialog", open_dialog)
        view = open_dialog["view"]
        # view.clear_items()
        await view.stop()
        # await data["message"].edit(view=view)
        # del self.interactable_messages[data["message"].id]

    async def close_dialog(self, message_id):
        '''removes interaction buttons from message to prevent further interactions starting from this dialog message'''
        #TODO: error edgecase handling
        #       View already expired/not there
        if message_id in self.interactable_messages:
            data = self.interactable_messages[message_id]
            print("Dialog Handler close dialog internal","message", message_id, "for dialog", data["dialog_name"])
            view = data["view"]
            view.clear_items()
            await data["message"].edit(view=view)
            del self.interactable_messages[message_id]

# since the interaction send_message doesn't return message that was sent by default, wrapper to get that behavior to be same as channel.send()
def interaction_send_message_wrapper(interaction):
    '''wrapper for sending a message to respond to interaction so that the message just sent is returned'''
    async def inner(**kwargs):
        await interaction.response.send_message(**kwargs)
        return await interaction.original_response()
    return inner

#custom button to always direct clicks to the handler because all information is there
class DialogView(ui.View):
    def __init__(self, handler, **kwargs):
        super().__init__(**kwargs)
        self.dialog_handler = handler

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
        await self.dialog_handler.handle_interaction(interaction)

class DialogSelect(ui.Select):

    def __init__(self, handler, **kwargs):
        print("DialogSelect init internal", kwargs)
        super().__init__(**kwargs)
        self.dialog_handler = handler

    async def callback(self, interaction):
        await self.dialog_handler.handle_interaction(interaction)

#testing pop up modals. copied from docs. this one allows clicker to input information. has to be done in response to interactions
class Questionnaire(ui.Modal, title='Questionnaire Response'):
    name = ui.TextInput(label='Name')
    answer = ui.TextInput(label='Potato', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Thanks for your response, {self.name}!', ephemeral=True)