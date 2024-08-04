# Nodetion
Currently on version Alpha 3.8.0.  
YAML format is functionally complete for alpha plans and mostly stable, but in alpha testing to discover use cases. !!!THIS IS YOUR WARNING THINGS ARE STILL A BIT ROUGH!!! Started and created as a system to manage interactive dialogs for a Discord bot, but further designed to extend to situations where the system waits for a variety of events with possibly multiple entities traversing the same graph layout.  
There are remnants of version 2.0, It is deprecated.  
Designed in collaboration with @e-a-h

## What is this project?
This project is a combination of the ideas that are in state machines, event simulation, and servers. You have the state machine part that graphs out what events are being waited for and what state you can transition to after event, as well as describing what to do when event happens and the current state data. The server part comes from the use case where there can be multiple concurrent users traversing the same graph and wanting to make sure updates are streamlined. State machine is implemented as Node classes and A central object termed a handler handles tracking the user data and processing received events and holds the graph.  

What's it capable of? 
* Nodes are entirely defined in YAML format config files. This makes it easy to define and swap out how the node behaves without reloading code. 
* Graphs can be split into multiple files. Files can be read and added to current graph or replace it
* Nodes use callbacks to customize behaviors. These are listed in yaml by name and the handler automatically tries to find and run the function. 
* Further expansion by writing custom functions can be done separate from the handler codebase and added to handler when running.
* Graph can be disjointed (not all nodes connected) and have multiple entry points
* Graph transitions are flexible. Nodes can list functions that define a condition, based on both event and saved data, under which transition can happen. Multiple transitions can happen from same event, potentially with different conditions. The original node can also remain open after an event causes a transition, similar to waiting for multiple survey aswers.
* multiple people moving through graph is tracked separately, custom event filter conditions can create custom groups of who is allowed to progress this node
* event occurances are sent to all nodes in handler, and filtered down to nodes where it is relevant.
* Event types can be defined. Early WIP! this can add custom requirements based on event type.
* Node types can be defined. Mid stage WIP! this can add custom requirements and behaviors based on node type.
* automatically cleans up nodes. All nodes have a lifetime to be waiting for events. Once it is up the system closes and cleans up the node. The lifetime can also be turned off.
* multiple handlers can be run at a time, even share a graph

# Table of Contents
- [Nodetion](#nodetion)
  - [What is this project?](#what-is-this-project)
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
  - [Handler Setup](#handler-setup)
  - [Custom Actions](#custom-actions)
  - [Creating Graph yaml](#creating-graph-yaml)
  - [Node Settings](#node-settings)
- [Developer Customizations](#developer-customizations)
  - [Setting up handlers](#setting-up-handlers)


# Running Example Dialog
Included in the example bot are a short yaml definition for an interactive QnA dialog done through Discord, showcase of how to integrate a DialogHandler with a discord bot, and examples of how to customize behaviors through the callback functions - in this case how to control a discord bot.

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
The building block of the state machine part of this project is a Graph Node. The Graph Node is where you are in the whole graph, and provides a blueprint for what events to wait for and what needs to be done to process instance specific data every single time this specific Graph Node is traversed by anyone. It is a description of what should happen at the least specific level. Yaml files contain a list of different Graph Nodes.   
When some event happens so that someone/thing needs to travel the graph, the system creates an active node counterpart for the graph node. Active nodes are responsible for data specific to this one traversal of the graph. Active nodes are linked to a graph node, and use it as instructions on where to go and what to do with the active node data. They represent a state of waiting. Waiting for events to happen, a decision, or a combination of multiple conditions. Since there can be multiple concurrent users, there can be multiple active nodes with the same graph node. Active nodes should only read, not change, graph node data.
In more detail, Active Nodes have subcomponents to hold data. Each active node generally holds data for one instance of being at a specific graph node. Traversing the graph will mean going from one Active Node to another (and most likely some different graph nodes). More on that in sessions.

## Node Types
Node types are a further layer above, an archetype for how graph nodes and their active counterparts are structured and behave. This can affect the structure of yaml for that node type and extra behaviors that must be done for that type even if not included in yaml. So the default "Base" type defines how all nodes that the handler works with should be structured.

## Sessions
Depending on situation some Active Node data is temporary - only for that node - and some needs to be kept while traversing. Sessions are meant for linking active nodes behaviors together and sharing data. There are yaml controls for this during transitions or starting at a node. Sessions hold data seprately from nodes and track nodes that are a part of them. They are especially useful for handing off data that can't be copied into each separate node

## Functions/Callbacks
The two names might be interchanged in documentation. These define the "how" part of custom behaviors for nodes in little resusable packets. An active node has a few different segments where it can call functions back, and each section does have requirements a function needs to meet to be used there. A function is default not allowed in sections but the programmer that wrote it can mark ok for specific sections when writing the function. They can be written to meet the requirements of multiple sections. More warnings for using them wrong in yaml coming soon. Some functions can take input from the yaml file as well. The structure of this data in yaml is dependent on the function definition. Most callback sections have different lists for each event type. This is to make sure the functions are the correct ones for the type. The one exception is the node enter callbacks that currently aren't separated by type

## Handler
A handler is the backbone and driver of this system's logic by receiving all input events, notifying active nodes, running nodes' custom behaviors/output, checking and performing transitions, storing all active nodes and their data, and storing available functions. Pretty much for any node to do anything, a handler needs to start it. Everything else is information for how to run the system, this does the running. Each handler has a graph to use and manage. This just tells it what area it should allow things to traverse within, plus everything else Graph Nodes define. The graph can be any shape, and can be loaded in from multiple files.

## Events
Events must go through the handler to trigger the correct behaviors and changes. To the handler, an event can be anything. All it needs is a name and the data. Only the functions will be concerned about event format, the handler doesn't deal with the specific data. It only passes the event to the nodes and to do that it only needs to know the event type so it can correctly categorize it. In yaml definitions, graph nodes list the event types that are listend to. So the biggest point to make sure events are happening is to make sure the event types in yaml are consistent with what is being passed into notify. Since events can be anything aka have any internal structure, the person writing yaml has to make sure the function they want to use can handle receiving the event and list it under the correct event type. You may have events that are a sub type of something else. Each ime the handler is notified it can only process either the subtype or the parent type. It does not notify nodes that are waiting for parent types of this event. Nodes in yaml may need to list out every subtype since systems might not be calling notify for both sub and parent.


# Operation Guide
This is the section for getting system running and building graphs. Majority of that configuration will be writing yaml for the nodes. More advanced edge cases and custom extensions are in a later section.

## Handler Setup
The bulk of work handling the running system happens in the `DialogHandler` class (located in file of same name in src)
This is the main item to instantiate.

Not too much data is needed to instantiate a handler object:
```python
import src.DialogHandler as DialogHandler
handler = DialogHandler.DialogHandler()
```
It needs more information to actually be helpful though! The first bit of data to pass into it is the graph. 
```python
handler.add_files(["file1", "file2"])
```
This adds on nodes from these files to what is already in handler, which was previously empty in this case. This is necessary for the handler to know where to allow people to go and what it should do. There is more information about customizing the nodes themselves in [Yaml definitions](#yaml-definitions). 

Next it also needs to know when events happen. The way that code will look will be very dependent on where the handler is being used. Event handling can take a while so this is an asynchronous function.
```python
async def on_message(message):
    await handler.handle_event("message_event", message)

async def on_select(selection):
    await handler.handle_event("selection_event", selection)
```
You give it the name of the event type first then the data! The name can by any string, just keep it consistent because it needs to match what is specified in the node definitions.

This is the basic setup for a handler, it knows the graph and will execute on an event happening. There are more customization optiosn and it could be more useful with extensions.

## Custom Actions
All custom behaviors nodes do are functions provided to the handler and listed by the Graph Nodes. There is a baisc set of functions automatically registered to handler, but oterwise any other features and extensions need to be added to be usable. There are a few options to do this. Further customization of system can involve writing your own custom callbacks. That is in the developers section.

`register_funciton` is the most basic how to add, the other register function methods work similarly.
this takes the function itself andand adds it to the internal registry of functions nodes can use.  
Optional advanced setting it takes is a dict of settings. The function itself should have settings defined on it. these control how it is used by handler. The overrides are provided if there's naming conflicts or other reason to override behavior.

`register_functions` takes dictionary mapping function reference to override settings. It can be used even if you don't need the advanced overrides. Just pass a blank dictionary.
`register_module` takes an imported file and assumes that the dictionary mapping is inside the file and named `dialog_func_info` and registers all functions listed there.

## Creating Graph yaml
The whole graph is described as a list of graph nodes with each graph node defining properties on itself. This list can be broken up however you want into separate files. Keep in mind rebuilding a graph from different files means you need to give all of those files to the same handler.

When creating a new file, it must have the key `nodes:` ot the top that points to a list of nodes. Any nodes outside this key will not be seen by the system. So the top of the file would look like:
```
nodes:
- id: Node1
  other settings for Node1 ...
- id: Node2
  other settings for Node2 ...
- id: Node3
  other settings for Node3 ...
```
This file would load 3 nodes into handler, the avaiable node settings will be shown in detail later. The rest of each node definition will be filled in starting at the same indentation level as the id.

Different Node types can add on different settings and structures to the yaml definitions. The base type does mean the basic structure of data the handler will need for nodes. One thing to keep in mind is each node type affects the structure of node, but does not affect the structure each function has for any values passed to it. aka nod type affects where you can put functions in node, but not settings the function needs.

Further tip, because of how the library used read yaml works, there's some cases that can have unexpected results for some people. If you have a value that you want to be just the text "yes" or "no" be sure to put quotes around it, or else it will be interpreted as True/False values.

## Node Settings
This is the fields, their accepted values, and nesting structure that Base type nodes version 3.8.0 accept. Note, the bolded are field names and what go before the colon.

* **id** -- A required string field for Graph Node, must be unique among all Graph Nodes in the same handler.
* **type** -- Optional string field, the field is optional but each Node has a type. By default all nodes are "Base" type Nodes. This field is only needed if you are sure you are using a different node type
* **version** -- Optional string field for the version of the node type the yaml is written for. Each Node type manages its own version number. For Base type, this is three integers separated by periods. If not specified, system assumes you wrote it for the most recent version of the node type. Recommend filling with the intended version number.
* **actions** -- an optional list of functions to call when the node is entered, either because starting the graph at that point or some other node transitioned here. The functions should be just the string name, or name as a key followed by the data to pass to it. basically all lists of functions work this way
* **TTL** -- optional field for Time To Live: length in seconds an active node for this Graph Node should wait for events before auto closing. Usually system starts timer when node is created and doesn't refresh it, so if a timer since last interaction is needed, put a refresh method in event actions list. -1 means node won't time out, use with caution. Base Type active nodes default to 3 minutes
* **graph_start** -- Optional field that holds settings for special event of starting the graph (little different from usual event handling settings). The presence of this key tells the handler it is ok to start the whole state machine at this point, and the sub elements are what type of events are allowed to cause that start. Start case also has a different order of handling than the rest of the node. An active version is created very early so functions from regular event handling can be reused here. Any setup callbacks are run first to setup the session since that would regularly be handled during a transition and the starting node may depend on a session. Filters are run after so any filters that depend on session data don't break and start can have similar filters to transition handling
  * any event name -- field that identifies an event type that can be processed and start the node. The name of event type will be the field name. Each event type can have a subsections of settings. graph_start is a dictionary, so each event type can only appear inside it once.
    * **session_chaining** -- optional field for controlling how new node interacts with session object. Only chaining action allowed here is "start" chaining which creates a session for node to start with. Value is either string "start" or a nested field specifying the session's TTL
        ```
        session_chaining: start
        ------- OR --------
        session_chaining:
          start: 34
        ```
    * **setup** -- an optional list of functions meant for performing actions that take the activated start node and event and setup session data if needed. Functions called here aren't gauranteed to run for a node that has passed filters to be tracked by handler
    * **filters** -- optional list of functions meant for filtering that take the activated start node and event. Returns whether the event can start at the node
* **close_actions** -- an optional field that holds settings for special event of closing the node. Is a list of functions to handle how to close and clean up the node that take the current node and event. Note closing can be because of timing out or closing after event or transition.
* **events** -- an optional field that holds settings for what types of events to listen to and how Active Node should respond.
  * any event name -- field that identifies an event type that can be processed on the node. The name of event type will be the field name. events is a dictionary, so each event type can only appear inside it once.
    * **filters** -- optional list of function names meant for filtering that take the current node and event. Returns if the incoming event is something this node should handle aka should trigger a response from the node. 
    * **actions** -- optional list of function names meant for performing actions that take the current node and event. Is what forms how the node responds to the event. This is the main section for changing node data due to event
    * **schedule_close** -- optional field whose value is one of "node", "session", or ["node", "session"]. setting for whether or not this node and/or session data should be closed and deleted after the event on this node is handled. This setting also appears in the transition settings and gets combined when there is a transition involved. see that for how they work together
    * **transitions** -- optional list of groups of settings that describes what node(s) to transition to and how after handling event on this node. Is nested inside each event type so only applies to that one type of event. When an event passes event filters, all the transitions listed under that event type are checked to see if transition filters pass. Each item is a single transition with settings:
      * **node_names** -- required field holding next node(s) to go to, either single or a list of multiple node identifiers (identifier as in the the value of the id field of the node). All nodes listed for one transition will be created as part of transition. If multiple copies of a node are needed, use node id as key and the value is how many copies.
        ```
        transitions:
        - node_names: node1
        - node_names: [test, node2]
        - node_names:
            - node1
            - test: 2
        - node_names:
            test: 2
        ```
      * **transition_counters** -- an optional list of functions that takes the current node and event.Is meant for adjusting what and how many nodes to transition to. node_names defines the baseline.
      * **transition_filters** -- an optional list of functions that takes the current node, event, and the name of the next node. Meant to decide if this specific event triggers this transition to happen. Runs once per node named in this transition
      * **transition_actions** -- optional list of functions takes the current node, event, and next node object. Meant to perform actions to handle the process of transitioning. This is the main section for changing node data based on transtion or handling any special cases of transferring data to next node.
      * **schedule_close** -- same as schedule close in the event: optional field whose value is one of "node", "session", or ["node", "session"]. Only the schedule_close settings for transitions that passed their filters are used when handling event. If either results from passed transitions' schedule_close or the event schedule close say to close, that thing will close.
      * **session_chaining** --  optional field for controlling how next nodes interact with session object. Chaining actions are "start", "chain", or "section" which respectively creates a new session for next node, adds next node to this node's session (does same thing as start if session doesn't exist on current node), or keeps the session data but closes existing nodes. Value is either the action name or a nested field specifying the session's TTL. When multiple transitions pass filters if there is one that sections session, the history will be closed and affect transitions that said chain. All session chaining are handled before callbacks. set schedule_close if session is not needed because this setting does not trigger cleaning up.

# Developer Customizations
WIP
you want to extend or customize core of project. topics to be included here: how to create custom Nodes, events, and callbacks.
Registering functions is needed as it tells the handler what is available for it to use.
only Functions you trust should be loaded into the handler since they can do anything to node or handler
Node Life cycle 

## Setting up handlers
There's already a written out example in `Extensions/Discord/ExampleBot.py` for some of the details! 

One thing the example does not have is if you are using custom Node types, these need to be registered before loading yaml so the parser can recognize them. Registration only needs to be done once per type, but double calls won't crash and burn. The registration call can be placed globally or in a function. The syntax is `register_node_type(moduleName, type_name)`. Registered node types will technically avialable to all handlers created, and there currently are no capabilities to limit types a handler can get from parsing. 

The handler will need to be instantiated to run. If there's references you want the handler to keep track of, pass them in as extra key value pairs, like how the example has `bot=self`. This setup allows callbacks to access the bot reference usiing the active node reference to handler.

There's a couple methods for loading in nodes. Graph nodes can be loaded before instantiating handler by directly using the parsing module's functions and passed into handler (by adding `nodes=your_list` to constructor), this does mean any handlers you pass it to will share the same graph, changes visible from each other. The example is going for a single handle with its own list, so it uses the handler's setup_from_files function. This function will override any current graph nodes and replace them with what was just read in.

Alongside the nodes, you want to register the functions that the handler can call. This can be done individually or in batches using modules. Modules do have a certain format to work. Functions will be added on, no deletions. Likely if adding to your own project you'll have to write a bacth of functions to integrate with said project. eg. the discord specific functions in the example.

Any methods that need to start a node or pass an event to handler need to be able to reference the handler object, so save it in an accessible place.  `main.py` shows a start process in response to Discord.py command calls. Here the event type is the same since there isn't much structural variation between each instance. `ExampleBot.py` shows notification calls instead. Here we broke up the Discord Interaction event type into multiple subtypes since they have slightly different data formats. Not needed to break down, it depends on how much you want your functions to deal with the difference, which may get messy. Notify event will go on to find all active nodes waiting for that `button_click` event or `select_menu` event etc. but start we know what node is needed.