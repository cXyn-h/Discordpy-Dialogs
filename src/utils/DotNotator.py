import copy
import typing

def parse_dot_notation_string(name, item, default=None, custom_func_name="custom_parse_dot"):
    '''
    Returns
    ---
    the object at the end of dot separated string name or default if list of names too long or something wasn't found. List too long includes getting to a type without keys when there's still names in the list.
    something wasn't found includes key not found in dictionary etc.'''
    split_names = name.split(".")
    return parse_dot_notation(split_names, item, default=default, custom_func_name=custom_func_name)
    

def parse_dot_notation(split_names: 'list[typing.Union[str, int]]', item, default=None, custom_func_name="custom_parse_dot"):
    '''Tries to find the object/value at the end of a list of field names or list indices recursively nested within item. Returns object or value found or default if not found.
    Default behavior of this is stepping through list and on each item searches for it in whatever item is at that layer, then using that result for further search.
    On each step checks for existance of function that overrides default search behavior and uses results of that if it works. See parameters section for details on this function, note that one search 
    can only use one specific custom name so it won't work well if objects in one search use different names for the custom override.
    Skips it and uses default behavior if function does not produce expected results. 
    Also searches within object's fields and functions and other attributes.
    
    Parameters
    ---
    - split_names - `list[str | int]`
        list of keys to search by. Works like a pointer chain. One key for grabbing one thing from object and one layer deeper
    - item - `Any`
        the item to search within
    - default - `Any | None`
        the value to return if not found
    - custom_func_name - `str`
        the name of the custom override function to use during this search. If any object while following list of pointers has this value, it tries to call it first.
        This custom function will be passed a copy of the remaining names to search.
        return from this function has to be either None or a tuple.
        If none is returned, this function will continue with default behavior. If a tuple the zeroth element is the remaining names to search, the first indexed is the object to continue search on.
        Empty names list means done with search and this will return the object immediately, otherwise can take as many names as needed off of the names list and dot parser will pick up from there with 
        the returned object until names are gone.
    
    Returns
    ---
    the object at the end of the list or default if list too long or something wasn't found. List too long includes getting to a type without keys when there's still names in the list.
    something wasn't found includes key not found in dictionary etc.'''
    recurse_data = item
    should_skip_custom = False
    # recurse to find object pointed to by name
    while len(split_names) > 0:
        if hasattr(recurse_data, custom_func_name) and not should_skip_custom:
            # has custom function defined on it, always want to try calling that first
            try:
                custom_found = getattr(recurse_data, custom_func_name)(copy.copy(split_names))
            except:
                # some error in function or something shared the same name that isn't a function. error means skip trying this
                should_skip_custom = True
                continue
            if custom_found == None:
                # something failed or object can't handle keys. try default way of grabbing instead
                # causes it to immediately loop and skip this section. object and name still same as was attempted here
                should_skip_custom = True
                continue
            try:
                remaining_keys, nested_obj = custom_found
            except:
                should_skip_custom = True
                continue
            if len(remaining_keys) == 0:
                # custom found exact object and ate all keys
                return nested_obj
            if remaining_keys == split_names and recurse_data is nested_obj:
                # should return None if can't handle, and should never return self object and same keys ever, but putting check just in case to prevent infinite loops
                    should_skip_custom = True
                    continue
            split_names = remaining_keys
            recurse_data = nested_obj
        elif isinstance(recurse_data, dict):
            # default way, when it is a dictionary get key
            next_key = split_names.pop(0)
            nested_data = recurse_data.get(next_key, None)
            if nested_data is None:
                return default
            recurse_data = nested_data
        elif isinstance(recurse_data, list):
            next_key = split_names.pop(0)
            try:
                num_key = int(next_key)
                recurse_data = recurse_data[num_key]
            except:
                # next data is a list, and the index does not work with list. error.
                return default
        elif type(recurse_data) not in [bool, str, int, float, type(None)]:
            # default way, when handling complex objects, try to get attribute
            next_key = split_names.pop(0)
            if not hasattr(recurse_data, next_key):
                return default
            else:
                next_step_data = getattr(recurse_data, next_key)
            recurse_data = next_step_data
        else:
            # hit unrecursible type before finishing recursions
            return default
        should_skip_custom = False
    return recurse_data