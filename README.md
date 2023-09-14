# Dialoguer (placeholder title)
Currently on version 3.6.0, in alpha testing to discover use cases. !!!THIS IS YOUR WARNING THINGS ARE STILL A BIT ROUGH!!! Started and created as a system to manage interactive dialogs for a discord bot, but further designed to extend to situations where the system waits for a variety of events with possibly multiple entities traversing the same graph layout. Version 2.0 is pretty much deprecated<br/>
Designed in collaboration with @e-a-h

__What is this project?__ <br />
This project is a combination of the ideas that are in state machines, event graphs, and servers. Nodes that make up a graph describe what events are being waited for, what to do when event happens, and what node(s) you can transition to after an event. Since this is an interactive dialog handler, there can be multiple concurrent users and events from interactions can have instance specific data while the graph stays the same. A central object termed a handler pairs with a graph to handle taking events from multiple concurrent users and track where they are and their session's data for the graph being handled.<br/>

What's it capable of? 
* Nodes are entirely defined in YAML (specific format for structuring text data) files. This makes it easy to define and swap out how the node behaves without reloading code. 
* Multiple yaml files can be used for one graph. Files can be read and added to current list of nodes or replace it
* Nodes use functions to customize behaviors. These are listed in yaml by name and the handler automatically tries to find and run the function. Further expansion by writing custom functions can be done separate from the handler codebase and added to handler when running.
* Graph can be disjointed (not all nodes connected) and have multiple entry points
* Graph transitions are flexible. Nodes can list functions that define a condition, based on both event and saved data, in which transition can happen. Multiple transitions can happen from same event, potentially with different conditions. The original node can also remain open after an event causes a transition, similar to waiting for multiple survey aswers.
* multiple people moving through graph is tracked separately, custom event filter conditions can create custom groups of who is allowed to progress this node
* event occurances are sent to all nodes in handler, and filtered down to nodes where it is relevant.
* Event types can be defined. WIP! this can add custom requirements based on event type.
* Node types can be defined. WIP! this can add custom requirements and behaviors based on node type.
* automatically cleans up nodes. All nodes have a lifetime to be waiting for events. Once it is up the system closes and cleans up the node. The lifetime can also be turned off.
* multiple handlers can be run at a time, even share a graph

# Table of Contents
- [Dialoguer (placeholder title)](#dialoguer-placeholder-title)
- [Table of Contents](#table-of-contents)
- [Running Example Dialog](#running-example-dialog)
- [System Concepts](#system-concepts)
  - [Nodes](#nodes)
  - [Node Types](#node-types)
  - [Sessions](#sessions)
  - [Functions/Callbacks](#functionscallbacks)
  - [Handler](#handler)
  - [Events](#events)
- [Operation Guide](#operation-guide)
  - [Creating Graph yaml](#creating-graph-yaml)
  - [Base Graph Node Fields](#base-graph-node-fields)
- [Developer Customizations](#developer-customizations)
  - [Setting up handlers](#setting-up-handlers)


# Running Example Dialog
Included in the Examples are a yaml definition for an interactive QnA dialog done through Discord, showcase of how to integrate a DialogHandler with a discord bot, and examples of how to customize behaviors through the callback functions - in this case how to control a discord bot. <br/>

Discord requires a token for bot to log in, and this project reads the token from a config.json located in the root of the project. After cloning repo, create a `config.json` file. Get bot token from dev portal and add it to file like this:
```
{
    token: "PASTE_TOKEN_BETWEEN_QUOTES"
}
```
run `main.py` to have a simple bot with a pre loaded dialog flow. Be sure to add the bot to a server and to a channel it can send messages in. Start dialog by sending `$menu` in a server channel.

# System Concepts
More high level information about this project's workings that could be helpful to understand for yaml writing
## Nodes
Yaml files contain a list of different graph nodes. Graph nodes provide a blueprint for what events to wait for and what needs to be done to process instance specific data every single time this specific graph node is traversed. They represent points on the map of transitions that is the graph. 
Once someone traverses through, the system creates an active node counterpart for the graph node. Active nodes will behave according to instructions in their linked graph node, and hold the instance specific data. They represent a state of waiting. Waiting for events to happen, a decision, or a combination of multiple conditions. Since there can be multiple concurrent users, there can be multiple active nodes with the same graph node. Active nodes will keep their data separate and should only read, not change, graph node data. Each active node can only belong to one handler.

## Node Types
Node types are a further layer above, defining how graph nodes and their active counterparts are structured. This can affect the structure of yaml for that node type and extra behaviors that must be done for that type even if not included in yaml. So the default "Base" type defines how all nodes that the handler works with should be structured.

## Sessions
Each active node's data is generally kept separate, but there are cases to link them together. Sessions are meant for linking active nodes behaviors together and sharing data, so there are yaml controls for this during transitions or starting at a node. Sessions hold data seprately from nodes and track nodes that are a part of them. They are especially useful for handing off data that can't be copied into each separate node

## Functions/Callbacks
The two names might be interchanged in documentation. These define the "how" part of custom behaviors for nodes in little resusable packets. An active node has a few different segments where it can call functions back, and each section does have requirements a function needs to meet to be used there. A function is default not allowed in sections but the programmer that wrote it can mark ok for specific sections when writing the function. They can be written to meet the requirements of multiple sections. More warnings for using them wrong in yaml coming soon. Some functions can take input from the yaml file as well. The structure of this data in yaml is dependent on the function definition. Most callback sections have different lists for each event type. This is to make sure the functions are the correct ones for the type. The one exception is the node enter callbacks that currently aren't separated by type

## Handler
A handler is the backbone and driver of this system's logic and data by receiving all input events, notifying nodes, activating nodes' custom behaviors/output, checking and performing transitions, storing all active nodes and their data, and storing available functions. Pretty much for any response, a handler needs to start it. It is a central point for defining what is allowed to run and happen in the given graph. Graph Nodes may be able to list out any function name, but that function only runs if the handler for that activation instance has the function loaded. Graph nodes may list out any node id to transition to but that transition only happens if the handler has loaded the next node. A single Yaml file can technically be loaded to different handlers, but only if the handler has loaded the neccessary type, and can be run if handler has the functions.

## Events
Events must go through the handler to trigger the correct behaviors and changes. The events a handler accepts can actually be anything with any data structure since the handler doesn't deal with the specific data. It only passes the event to the nodes and to do that it only needs to know the event type so it can correctly categorize it. In yaml definitions, graph nodes list the event types that are listend to. So the biggest point to make sure events are happening is to make sure the event types in yaml are consistent with what is being passed into notify. Since events can be anything aka have any internal structure, the person writing yaml has to make sure the function they want to use can handle receiving the event and list it under the correct event type. You may have events that are a sub type of something else. Each ime the handler is notified it can only process either the subtype or the parent type. It does not notify nodes that are waiting for parent types of this event. Nodes in yaml may need to list out every subtype since systems might not be calling notify for both sub and parent.


# Operation Guide
A large chunk of using this project will need some yaml writing. Custom extensions are in a later section.

## Creating Graph yaml
The whole graph is described as a list of graph nodes. This list can be broken up however you want into separate files. If broken apart the files will need to all be loaded into the same handler. Here the nodes are responsible for defining how to handle transitions. 

when creating a new yaml file, it must have the key `nodes:` ot the top that points to a list of nodes. Any nodes outside this key are ignored. So a small stub of a file would look like: <br/>
```
nodes:
 - id: Node1
   other settings for Node1 ...
 - id: Node2
   other settings for Node2 ...
 - id: Node3
   other settings for Node3 ...
```
This file loads 3 nodes into handler.
The rest of each node definition will be filled in starting at the same indentation level as the id. Structure might be different based on node type, but at least there's a base to use. See below for what structure base node settings are expected in. each function also defines its own structure for any values passed to it.

Further tip, because of how the library used read yaml works, there's some cases that can have unexpected results for some people. If you have a value that you want to be just the text "yes" or "no" be sure to put quotes around it, or else it will be interpreted as True/False values.

## Base Graph Node Fields
required fields and data format for the system to parse nodes
* **id** -- required string identifier for node, must be unique among all nodes in the same handler, as that's how the handler finds this node
* **type** -- This string field itself is optional, but each node has a type. By default all nodes are "Base" type nodes. This field is only needed if you are sure you are using a custom node definition
* **v or version** -- two names for same thing. Each node type can have a specific version to track their changes separately from each other. This optional field is a text sring for the version the yaml is written for. Three integers separated by periods. If not specified, system assumes you wrote it for the most recent version of the node.
* **actions** -- an optional list of functions to call when the node is entered, either because starting the graph at that point or some other node transitioned here. The functions should be just the string name, or name as a key followed by the data to pass to it. basically all lists of functions work this way
* **TTL** -- optional setting for Time To Live: length in seconds this node should wait for events before auto closing. Base type defaults to 3 minutes
* **graph_start** -- an optional special case of event handling with limited fields allowed inside of it. The presence of this key tells the handler it is ok to start the whole state machine at this point, and the sub elements are what type of events are allowed to cause that start. Start case also has a different order of handling than the rest of the node. An active version is created very early so functions can be reused here. Any setup callbacks are run first to setup the session since that would regularly be handled during a transition and the starting node may depend on a session. Filters are run after so any filters that depend on session data don't break and start can have similar filters to transition handling
  * **session_chaining** -- option field whose only allowed value is "start" here. Wether or not a session will be created for node to start with
  * **setup** -- an optional list of functions that take the activated start node and event and setup session data if needed, functions called here aren't gauranteed to run for a node that has passed filters and is fully tracked by handler
  * **filters** -- optional list of functions that take the activated start node and event to determine if the event can start at the node
* **close_actions** -- an optional special case of event. a list of functions to handle how to close and clean up the node. Closing can be because of timing out or closing after event or transition.
* **events** -- an optional key where the sub elements are more keys for the types of events that this node listens to. For each event type there are more settings to control behaviors
  * **filters** -- optional list of functions that take the current node and event to determine if the incoming event should trigger a response from the node. 
  * **actions** -- optional list of functions that take the current node and event, and which effectively is how the node responds to the event. this is the main section for changing node data due to event
  * **schedule_close** -- optional field whose value is one of "node", "session", or ["node", "session"]. setting for whether or not this node and/or session data should be closed and deleted after the event on this node is handled. This setting also appearts in the transition settings. see that for how they work together
  * **transitions** -- optional list nested in each event type that describes settings for how to make a transition to next node. When an event happens all the transitions listed under that event type are filtered every time. Each item is a single transition with settings:
    * **node_names** -- required identifier of next node to go to or a list of multiple node identifiers. list is handy when the process to handle transitioning to multiple nodes is the same.
    * **transition_filters** -- an optional list of functions that takes the current node, event, and the name of the next node to decide if this specific event triggers this transition to happen
    * **transition_actions** -- optional list of functions that takes the current node, event, and next node object to handle the process of transitioning. This is the main section for changing node data based on transtion or handling any special cases of transferring data to next node.
    * **schedule_close** -- same as schedule close in the event. Since this can appear in multiple transitions and there can be multiple transitions per event on a node, only the schedule_close settings for transitions that passed their filters are considered. If either results from passed transitions' schedule_close or the event schedule close say to close, that thing will close.
    * **session_chaining** -- this optional setting is one of "start", "chain", "section" for create a new session for next node, add next node to this node's session (does same thing as start if session doesn't exist on current node), or keep the session data but close out existing nodes. when multiple transitions pass filters, if there is one that sections session, the history will be closed and affect transitions that said chain. All session chaining are handled before callbacks. set schedule_close if session is not needed because this setting does not trigger cleaning up.

# Developer Customizations
WIP
you want to extend or customize core of project. topics to be included here: how to create custom Nodes, events, and callbacks.
Registering functions is needed as it tells the handler what is available for it to use.
only Functions you trust should be loaded into the handler since they can do anything to node or handler
Node Life cycle 

## Setting up handlers
There's already a written out example in `Examples/ExampleBot.py` for some of the details! 

One thing the example does not have is if you are using custom Node types, these need to be registered before loading yaml so the parser can recognize them. Registration only needs to be done once per type, but double calls won't crash and burn. The registration call can be placed globally or in a function. The syntax is `register_node_type(moduleName, type_name)`. Registered node types will technically avialable to all handlers created, and there currently are no capabilities to limit types a handler can get from parsing. 

The handler will need to be instantiated to run. If there's references you want the handler to keep track of, pass them in as extra key value pairs, like how the example has `bot=self`. This setup allows callbacks to access the bot reference usiing the active node reference to handler.

There's a couple methods for loading in nodes. Graph nodes can be loaded before instantiating handler by directly using the parsing module's functions and passed into handler (by adding `nodes=your_list` to constructor), this does mean any handlers you pass it to will share the same graph, changes visible from each other. The example is going for a single handle with its own list, so it uses the handler's setup_from_files function. This function will override any current graph nodes and replace them with what was just read in.

Alongside the nodes, you want to register the functions that the handler can call. This can be done individually or in batches using modules. Modules do have a certain format to work. Functions will be added on, no deletions. Likely if adding to your own project you'll have to write a bacth of functions to integrate with said project. eg. the discord specific functions in the example.

Any methods that need to start a node or pass an event to handler need to be able to reference the handler object, so save it in an accessible place.  `main.py` shows a start process in response to Discord.py command calls. Here the event type is the same since there isn't much structural variation between each instance. `ExampleBot.py` shows notification calls instead. Here we broke up the Discord Interaction event type into multiple subtypes since they have slightly different data formats. Not needed to break down, it depends on how much you want your functions to deal with the difference, which may get messy. Notify event will go on to find all active nodes waiting for that `button_click` event or `select_menu` event etc. but start we know what node is needed.