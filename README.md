# Discordpy-Dialogs-alpha
alpha version to mess around with creating a system to manage interactive dialogs for a discord bot

Now on Version 3.5.0, with a big overhaul to how nodes are structured from previous versions. Documentation to come soon.



# Version 2 Documentation
## Running Example Dialog
This project reads the token for connecting to Discord from config.json. After copying, create a `config.json` file. Get bot token from dev portal and add it to file like this:
```
{
    token: "PASTE_TOKEN_BETWEEN_QUOTES"
}
```
run main.py to have a simple bot with a pre loaded dialog flow with responses with button choices and a modal form. Start dialog by sending `!test` in a server channel
For the reply nodes, a simple test to make sure responses are received and next node is sent is triggered with `!testmr`. see terminal printout for changes to saved data, since the formatting for submitted information is WIP.


## Adding to other bots
DialogHandler will need to be instantiated. Any methods that need to start a dialog need to be able to reference the handler object. Making a field of the bot like in the example works well. Reply nodes require message Intent, since they wait for a sent message in channel. If those nodes are neded, add the intent first. Handler also needs to receive message events, so add the handler's on_message function as event listener or call it from bot's on_message.  
From further testing, handler also has to listen to interaction events. 

## calling into Graph
To start a conversation and tracking any progress needed, call handler.start_at("node", object). First pass in id of node to start at, if the node id is not loaded into handler, it will not start anything. The second argument is the context or interaction or message that provides context for starting the conversation flow. for versions alpha2.0 and before it is used to find where to send the next node, who sent the object to help nodes filter out who is allowed to progress the node, and if it is an interaction object it will be responded to.

## Creating Dialog yamls
The biggest part of this project is being able to customize what is done and the flow of progress in a easy manner. This is saved and defined in yaml files. The example dialog flow is all defined in `testDialogs.yaml` and shows most all the different possible ways to create each of the items. Some terms first: A node is either a dialog or a modal and represents some action done and are now waiting for a choice to be made, currently only the user in chat can do this. Multiple nodes can be defined in one file (do this by listing each node as one element in list), and multiple files loaded into one Handler. The parsing will throw errors if data is formatted incorrectly. Here are the fields that need to be listed out in a yaml file.

### Dialog Node
A node that is a message in chat with the saved prompt as the content and displays a button for each option waiting for one to be clicked
* type -- "type":"dialog" is optional because default is create a dialog node
* id  -- must have. internal id for this dialog, must be unique among all loaded nodes
* prompt -- the text to prompt person for a response
* 0-1 command -- callback function called after this dialog is sent
* 0-25 (because Discord set this limit) options -- represents what can be selected as next steps. currently all displayed as a button. See option Section for possible configuration.

### Option
Ties in with the dialog node. stores data representing a possible choice that can be made and callback command and next node to go to
* label -- must have. the text to show on the button
* id -- must have. the custom ID. IDs must be unique for all options in the same dialog. 
* 0-1 next_node -- what next node to send if selecting this option should cause another thing to happen. These can be defined in line or reference a node defined elsewhere by using the name.
* 0-1 data -- can have any sub fields, really up to how programmer wants to use these in callbacks. behaves same as flag
* 0-1 flag -- represents information that should be carried as context for following dialogs. stays saved until end flag is found.
* 0-1 command -- callback function called after option is selected
* 0-1 end -- tells handler to throw out saved data for this dialog flow for user that interacted.

### Modal Node
A node that represents waiting for a user to submit information through a discord modal (pop up window) with multiple text boxes to submit information in
* type -- must have "type":"modal" to create a modal node
* title -- must have. title to be shown on the top of modal window
* id -- must have. internal id for this modal, must be unique among all loaded nodes
* 1-5 fields -- list of text inputs boxes to add to the modal. see Modal Fields section for possible configuration
* 0-1 submit_callback -- callback function called right after hitting submit modal
* 0-1 next_node -- same as option next node, what should happen next
* 0-1 data -- same as option data
* 0-1 flag -- same as option flag
* 0-1 end -- same as option end.

### Modal Fields
Specific to modal nodes. Represents settings for how to display the text boxes in a modal and various other behavior settings. All of these are parameters that discord.py accepts to configure text boxes (default_value is renamed from default), just made avaiable to be configued through yaml files
* id -- must have. custom id for the text box
* label -- must have. the name of the box that will be displayed on top of box
* default_value -- what this text box will be filled in with by default when window is first opened
* max_length -- max length of text that can be submitted
* min_length -- minimul lenth of text that has to be submitted
* placeholder -- the grayed out background text to show when box is empty
* required -- is filling out this box required
* style -- "short", "paragraph" or "long". alters height of text box. either one line or multiple for "paragrah" or "long"

### Reply Node
it needs a better name. A node that is waiting for user to reply by sending a message in chat. Useful for sending data that can't be done through modal (images)
* type -- must have "type":"reply" to create a reply node
* id -- must have. internal id for this node, must be unique among all loaded nodes
* 0-1 prompt -- the text to prompt person for a response. if none saved uses a default "Please type response in chat"
* 0-1 submit_callback -- callback function called right after a message is recognized as a valid response to this node
* 0-1 next_node -- same as option next node, what should happen next
* 0-1 data -- same as option data
* 0-1 flag -- same as option flag
* 0-1 end -- same as option end.

## Additional Notes
DialogHandler.py's load_file handles correctly formatting input from yaml files into objects, saving isn't implemented yet.
DialogHandler is meant to be instantiated and hold lists of which dialogs it can send, which callbacks it is allowed to call, and which dialogs are waiting for user input. Multiple files can be written and loaded, not much error checking if there's overlap currently. Technically more than one instance can be made and run, but not tested yet.
The saved data dictionary keys are a tuple of userid and which dialog they need to answer next. There's a bit of different behavior when there is saved data. User interacting with dialogs can't backtrack to previous steps if there is saved data. It's finish it or restart from the start of that section. The handler recongnizes a next step as when the next message has more than 0 options. Otherwise the dialogs stay open and any branch of dialog can be taken until the buttons time out.
Further thoughts are written as TODOs