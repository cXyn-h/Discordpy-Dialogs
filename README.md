# Discordpy-Dialogs-alpha
alpha version to mess around with creating a system to manage interactive dialogs for a discord bot


## Getting Started
after copying, create a `config.json`. it only needs one field: token. get bot token from dev portal and paste it in there
```
{
    token: "PASTE_TOKEN"
}
```
run main.py to have a simple bot with a pre loaded test dialog. start the dialog with `!test`


## Use
Dialogs that the system can use is specified through yaml or dictionaries. testDialogs.yaml and DialogHandler.py's init have examples. DialogHandler.py's load_file handles correctly formatting input from yaml files into objects. All dialogs must be named, and all options have a display string and id. 
DialogHandler is meant to be instantiated and hold lists of which dialogs it can send, which callbacks it is allowed to call, and which dialogs are waiting for user input. Multiple files can be written and loaded, not much error checking if there's overlap currently. Technically more than one instance can be made and run, but not tested yet.


Documentation is mostly in code files. 
