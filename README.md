# Discordpy-Dialogs-alpha
alpha version to mess around with creating a system to manage interactive dialogs for a discord bot


## Running Example Dialog
This project reads the token for connecting to Discord from config.json. After copying, create a `config.json` file. Get bot token from dev portal and add it to file like this:
```
{
    token: "PASTE_TOKEN_BETWEEN_QUOTES"
}
```
run main.py to have a simple bot with a pre loaded test dialog. Start dialog by sending `!test` in a server channel


## Adding to other bots
DialogHandler will need to be instantiated. Any methods that need to start a dialog need to be able to reference the handler object.

## Creating Dialog yamls
Dialogs are saved in yaml files. The example dialog flow is all defined in `testDialogs.yaml`. Multiple dialogs can be defined in one file, and multiple files loaded into one Handler.
Dialog definition:  
* name  -- must have. how to reference this dialog
* prompt -- the text to prompt person for a response
* 0 or 1 command -- callback function called after this dialog is sent
* 0-25 (because Discord set this limit) options -- represents what can be selected as next steps. currently all displayed as a button
Option:  
* label -- must have. the text to show on the button
* id -- must have. the custom ID. IDs must be unique for all options in the same dialog. 
* 0-1 dialog -- what dialog to send if selecting this option should cause a dialog to be sent in response. These can be defined in line or reference a dialog defined elsewhere by using the name.
* 0-1 data -- can have any sub fields, really up to how programmer wants to use these in callbacks. behaves same as flag
* 0-1 flag -- represents information that should be carried as context for following dialogs. saved until end flag is found.
* 0-1 command -- callback function called after option is selected
* 0-1 end -- tells handler to throw out saved data for this dialog flow for user that interacted.

## Additional Notes
DialogHandler.py's load_file handles correctly formatting input from yaml files into objects, saving isn't implemented yet.
DialogHandler is meant to be instantiated and hold lists of which dialogs it can send, which callbacks it is allowed to call, and which dialogs are waiting for user input. Multiple files can be written and loaded, not much error checking if there's overlap currently. Technically more than one instance can be made and run, but not tested yet.
The saved data dictionary keys are userid and which dialog they need to answer next. There's a bit of different behavior when there is saved data. User interacting with dialogs can't backtrack to previous steps if there is saved data. It's finish it or restart from the start of that section. The handler recongnizes a next step as when the next message has more than 0 options. Otherwise the dialogs stay open and any branch of dialog can be taken until the buttons time out.
Still are lots of TODOs for added features
