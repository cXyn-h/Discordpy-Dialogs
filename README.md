# Dialoguer (placeholder title)
Currently on alpha version 3.5.0. !!!THIS IS YOUR WARNING THINGS ARE STILL A BIT ROUGH!!! Created to mess around with a system to manage interactive dialogs for a discord bot. <br/>
This is a cross between a state machine and a server that tracks sessions for users. It loads one copy of the state machine as a map of how users can interact with bot, then have a central object tracking where individual instances/users are and their data. Designed to be configurable and extensible with all nodes defined through yaml and ability to add custom functions to hook into lifecycle. Discord integration is done through these functions. The graph can be disjointed and have multiple starting points. <br/>

Now on Version 3.5.0, with a big overhaul to how nodes are structured from previous versions. Documentation is WIP.

## Running Example Dialog
Included in the Examples are a yaml definition for an interactive QnA dialog done through Discord, showcase of how to integrate a DialogHandler with a discord bot, and WIP examples of how to customize behaviors through the callback functions (in this case how to control discord bot). <br/>
Discord requires a token for bot to log in, and this project reads the token from a config.json located in the root of the project. After cloning repo, create a `config.json` file. Get bot token from dev portal and add it to file like this:
```
{
    token: "PASTE_TOKEN_BETWEEN_QUOTES"
}
```
run main.py to have a simple bot with a pre loaded dialog flow. Be sure to add the bot to a server and to a channel it can send messages in. Start dialog by sending `$menu` in a server channel.

# Concepts
Nodes represent a state of waiting. Waiting for a events to happen, waiting for a decision, or waiting for multiple things. 
A handler is the central point storing which nodes are still waiting for events and their context data. It handles receiving events and activating the callbacks and transitions of nodes.
WIP


# Operatorion Guides
Using this project means lots of writing yaml. All node config like what they are waiting for, how to respond to events, and what node(s) to go to next are described in a yaml object and loaded in at run time. There's already a base node type that stores and handles the above list included so no extensions needed. Custom extensions are in a later section.
## Creating Graph yaml
The whole state machine is described as a list of nodes. This list can be saved within the same file or can be broken up however you want into separate files. If broken apart remember to load all the files into the same handler. <br/>
when creating a new file, it must have the key `nodes:` ot the top that points to a list of nodes. Any nodes outside this key are ignored. So a small stub of a file would look like: <br/>
```
nodes:
 - id: Node1
   other settings for Node1 ...
 - id: Node2
   other settings for Node2 ...
 - id: Node3
   other settings for Node3 ...
 ...
```
This file loads 3 nodes into handler

## Node Definition
required fields and data format for the system to parse nodes
* **id** -- required string id for node, must be unique among all nodes in the same handler, as that's how the handler finds this node
* **type** -- This string field itself is optional, but each node has a type. By default all nodes are "Base" type nodes. This field is only needed if you are sure you are using a custom node definition
* **v or version** -- two names for same thing. Each node type can have a specific version to track their changes separately from each other. This optional field is a text sring for the version the yaml is written for. Three integers separated by periods. If not specified, system assumes you wrote it for the most recent version of the node.
* **callbacks** -- an optional list of functions to call when the node is entered, either because starting the graph at that point or some other node transitioned here. The functions should be just the string name, or name as a key followed by the data to pass to it. basically all lists of functions work this way
* **events** -- an optional key where the sub elements are more keys for the types of events that this node listens to. For each event type there are more settings to control behaviors
  * **filters** -- optional list of functions that take the current node and event to determing if the incoming event should trigger a response from the node. 
  * **callbacks** -- optional list of functions that take the current node and event, and which effectively is how the node responds to the event. this is the main section for changing node data due to event
  * **schedule_close** -- optional field whose value is one of "node", "session", or ["node", "session"]. setting for whether or not this node and/or session data should be closed and deleted after the event on this node is handled. This setting also appearts in the transition settings. see that for how they work together
  * **transitions** -- optional list nested in each event type that describes settings for how to make a transition to next node. When an event happens all the transitions listed under that event type are filtered every time. Each item is a single transition with settings:
    * **node_names** -- required name of next node to go to or a list of multiple node names. list is handy when the process to handle transitioning to multiple nodes is the same.
    * **transition_filters** -- an optional list of functions that takes the current node, event, and the name of the next node to decide if this specific event triggers this transition to happen
    * **transition_callbacks** -- optional list of functions that takes the current node, event, and next node object to handle the process of transitioning. This is the main section for changing node data based on transtion or handling any special cases of transferring data to next node.
    * **schedule_close** -- same as schedule close in the event. Since this can appear in multiple transitions and there can be multiple transitions per event on a node, only the schedule_close settings for transitions that passed their filters are considered. If either results from passed transitions' schedule_close or the event schedule close say to close, that thing will close.
    * **session_chaining** -- sessions link nodes together and allow them to share data. this optional setting is one of "start", "chain", "section" for create a new session for next node, add next node to this node's session (does same thing as start if session doesn't exist on current node), or keep the session data but close out existing nodes. Basically how shared data will be shared with next node and how next node will link to previous. set schedule_close if either node or session are not needed because this setting does not trigger cleaning up.
* **TTL** -- optional setting for how long in seconds this node should wait for events before auto closing. Base type defaults to 3 minutes
* **start** -- an optional special case of event. it has the same structure except only filter callbacks are allowed. The presence of this key tells the handler it is ok to the whole state machine at this point, and the sub keys are what type of events are allowed to cause that start. These are filters for whether or not the event can start the graph at the node.
* **close_callbacks** -- an optional special case of event. a list of functions to handle how to close and clean up the node. Closing can be because of timing out or closing after event or transition.

# Developer Customizations
you want to extend or customize core of project. topics to be included here: how to create custom Nodes, events, and callbacks. WIP

# Version 2 Documentation

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