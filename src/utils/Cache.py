import typing
import copy
from datetime import datetime, timedelta
import asyncio
import uuid
from enum import Enum

from src.utils.Enums import CLEANING_STATE
# for better logging
import logging
import sys

cachev2_logger = logging.getLogger('dev-Cachev2')
if not cachev2_logger.hasHandlers():
    logging_handler = logging.StreamHandler(sys.stdout)
    logging_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
    logging_handler.setFormatter(logging_format)
    cachev2_logger.addHandler(logging_handler)
cachev2_logger.setLevel(logging.INFO)

cleaning_logger = logging.getLogger("Cache Cleaning")
if not cleaning_logger.hasHandlers():
    logging_handler = logging.StreamHandler(sys.stdout)
    logging_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
    logging_handler.setFormatter(logging_format)
    cleaning_logger.addHandler(logging_handler)
cleaning_logger.setLevel(logging.INFO)

# goal of this system is to support many to many key and object relationship, have secondary key tracking be self managed, 
#   and stop dealing with nested dicts and having to check each layer exists when trying to do anything with it

class AbstractIndex:
    '''all methods in this need to be overridden. Indices should manage its own way of storing mapping of its secondary keys to the primary keys.
    Index will need to be added to a `MultiIndexer` object to receive data change events. `MultiIndexer` will notify this index of data changes through the
    `add_item`, `remove_item`, and `set_item` callbacks.'''
    def __init__(self, name) -> None:
        self.name = name

    def get(self, key, default=None):
        '''returns copy of list of primary keys that fit the given key in this index, or the default value if not found'''
        pass
    
    def clear(self):
        '''clear data stored by index'''
        pass

    def get_item_secondary_keys(self, item):
        '''find all secondary keys that this index would track for the given item. aka what secondary keys this index will use to refer to item'''
        return []

    def add_item(self, primary_key, item):
        '''callback when item has been added to data stores under given primary key and needs to be added to index tracking.'''
        pass

    def remove_item(self, primary_key, item):
        '''callback when item under given primary key has been removed from data stores and index tracking also needs to update'''
        pass

    def set_item_keys(self, primary_key, old_second_keys, item):
        '''callback when item under given primary key has had its internal data updated. During a set, the index needs to be passed what secondary key 
        data it should check and clean up. This method uses the secondary keys for this object before update'''
        pass

    def _set_item_data(self, primary_key, old_item, item):
        '''callback when item under given primary key has had its internal data updated. During a set, the index needs to be passed what secondary 
        key data it should check and clean up. This method uses the whole object before update'''
        return self.set_item_keys(primary_key, self.get_item_secondary_keys(old_item), item)


class FieldValueIndex(AbstractIndex):
    '''simple usable implementation of index. pass in period separated `column_name` to have it search for secondary keys in nested 
    objects and dictionaries. if `column_name` points to list or dictionary, index uses list items and dictionary keys as the secondary keys.
    add a function called `indexer` that returns keys or None if cannot handle to override this index's default behavior'''
    def __init__(self, name, column_name:str) -> None:
        super().__init__(name)
        self.column_name = column_name
        self.pointers:dict[typing.Hashable, set[typing.Hashable]] = {}
        '''secondary key to set of primary keys that contain the secondary key as a value'''

    def get(self, key, default=None):
        return copy.deepcopy(self.pointers.get(key, default))
    
    def clear(self):
        self.pointers.clear()

    def _add_pointers(self, primary_key, secondary_keys):
        for secondary_key in secondary_keys:
            if secondary_key not in self.pointers:
                self.pointers[secondary_key] = set()
            self.pointers[secondary_key].add(primary_key)

    def _remove_pointers(self, primary_key, secondary_keys):
        for secondary_key in secondary_keys:
            if secondary_key in self.pointers and primary_key in self.pointers[secondary_key]:
                # prevent errors trying to remove something not in there
                self.pointers[secondary_key].remove(primary_key)
            if secondary_key in self.pointers and len(self.pointers[secondary_key]) < 1:
                del self.pointers[secondary_key]

    def add_item(self, primary_key, item):
        self._add_pointers(primary_key, self.get_item_secondary_keys(item))

    def remove_item(self, primary_key, item):
        self._remove_pointers(primary_key, self.get_item_secondary_keys(item))
    
    def set_item_keys(self, primary_key, old_second_keys, item):
        self._remove_pointers(primary_key, old_second_keys)
        self.add_item(primary_key, item)
    
    def get_item_secondary_keys(self, item):
        # indexer method is meant as a way for objects to define how it wants to handle grabbing data for indexing for all or subset of keys when indexing is based on what data is contained within the object
        #   input is a list of the keys to recursively search for
        #   return format is None or a tuple of format: first is the list of remaining keys to recurse on, the second is the object to recurse in if there's still keys or the exact list of secondary keys to use if no more recursing is needed
        #   inmplementation can override default search way and return the exact keys that are wanted. have to put `return [], <list of secondary keys>`
        #   implementation can recurse a couple layers but not all the way. the function will continue to recurse at the point that was returned. 
        #   implementation can ignore what was input and just not handle at all, return None
        recurse_data = item
        split_names = self.column_name.split(".")
        should_skip_indexer = False
        # part one is recursing to find where the column name points to, then part two sorting out what the keys are in that data
        while len(split_names) > 0:
            if hasattr(recurse_data, "indexer") and not should_skip_indexer:
                # indexer method is meant as a way for objects to define how it wants to handle grabbing data for indexing for all or subset of keys when indexing is based on what data is contained within the object 
                # try that first and if fails try the default ways
                indexer_returned = recurse_data.indexer(copy.copy(split_names))
                if indexer_returned is None:
                    # something failed or can't handle keys. try default way of grabbing instead
                    should_skip_indexer = True
                    continue
                remaining_keys, nested_obj = indexer_returned
                if len(remaining_keys) == 0:
                    # the custom indexer was able to take all keys aka found secondary keys and done. assuming and trusting indexer to find exactly what keys it needs in this case
                    return nested_obj
                if remaining_keys == split_names and recurse_data is nested_obj:
                    # should return None if can't handle, and should never return self object and same keys ever, but putting check just in case to prevent infinite loops
                    should_skip_indexer = True
                    continue
                recurse_data = nested_obj
                split_names = remaining_keys
            elif isinstance(recurse_data, dict):
                # default way, when it is a dictionary get key
                next_key = split_names.pop(0)
                nested_data = recurse_data.get(next_key, None)
                if nested_data is None:
                    return []
                recurse_data = nested_data
            elif type(recurse_data) not in [list, bool, str, int, float, type(None)]:
                # default way, when handling complex objects, try to get attribute
                next_key = split_names.pop(0)
                if next_key == "class":
                    # maybe want to have things that are python defaults have custom search names? make it less dependent on language structure
                    next_step_data = recurse_data.__class__.__name__
                elif not hasattr(recurse_data, next_key):
                    return []
                else:
                    next_step_data = getattr(recurse_data, next_key)
                recurse_data = next_step_data
            else:
                # hit unrecursible type before finishing recursions
                return []
            should_skip_indexer = False

        # reached the end of keys to search at so whatever data or object is left is where the keys are/inside, now do the default way of sorting through data to get keys.
        result_keys = set()
        if type(recurse_data) not in [dict, list, bool, str, int, float]:
            # found data is a complex object, probably some way to get keys but don't really have a default way so giving up. return blank
            return []
        elif isinstance(recurse_data, list):
            # uses list items as keys. only grabs hashable items, shouldn't have non-hashables inside anyways
            for item in recurse_data:
                try:
                    result_keys.add(copy.deepcopy(item))
                except:
                    pass
        elif isinstance(recurse_data, dict):
            # uses dict keys as keys. 
            for item in recurse_data.keys():
                result_keys.add(copy.deepcopy(item))
        else:
            # data is a bool, int, str etc. primitive type and hashable
            try:
                result_keys.add(recurse_data)
            except:
                pass
        return list(result_keys)
    
class ObjContainsFieldIndex(FieldValueIndex):
    def __init__(self, name, column_name: str) -> None:
        super().__init__(name, column_name)
        self.pointers["does"] = set()
        self.pointers["not"] = set()

    def get_item_secondary_keys(self, item):
        # indexer method is meant as a way for objects to define how it wants to handle grabbing data for indexing for all or subset of keys when indexing is based on what data is contained within the object
        #   input is a list of the keys to recursively search for
        #   return format is None or a tuple of format: first is the list of remaining keys to recurse on, the second is the object to recurse in if there's still keys or the exact list of secondary keys to use if no more recursing is needed
        #   inmplementation can override default search way and return the exact keys that are wanted. have to put `return [], <list of secondary keys>`
        #   implementation can recurse a couple layers but not all the way. the function will continue to recurse at the point that was returned. 
        #   implementation can ignore what was input and just not handle at all, return None
        recurse_data = item
        split_names = self.column_name.split(".")
        should_skip_indexer = False
        # part one is recursing to find where the column name points to, then part two sorting out what the keys are in that data
        while len(split_names) > 0:
            if hasattr(recurse_data, "indexer") and not should_skip_indexer:
                # indexer method is meant as a way for objects to define how it wants to handle grabbing data for indexing for all or subset of keys when indexing is based on what data is contained within the object 
                # try that first and if fails try the default ways
                indexer_returned = recurse_data.indexer(copy.copy(split_names))
                if indexer_returned is None:
                    # something failed or can't handle keys. try default way of grabbing instead
                    should_skip_indexer = True
                    continue
                remaining_keys, nested_obj = indexer_returned
                if len(remaining_keys) == 0:
                    # the custom indexer was able to take all keys aka found secondary keys and done. assuming and trusting indexer to find exactly what keys it needs in this case
                    return ["does"]
                if remaining_keys == split_names and recurse_data is nested_obj:
                    # should return None if can't handle, and should never return self object and same keys ever, but putting check just in case to prevent infinite loops
                    should_skip_indexer = True
                    continue
                recurse_data = nested_obj
                split_names = remaining_keys
            elif isinstance(recurse_data, dict):
                # default way, when it is a dictionary get key
                next_key = split_names.pop(0)
                nested_data = recurse_data.get(next_key, None)
                if nested_data is None:
                    return ["not"]
                recurse_data = nested_data
            elif type(recurse_data) not in [list, bool, str, int, float, type(None)]:
                # default way, when handling complex objects, try to get attribute
                next_key = split_names.pop(0)
                if next_key == "class":
                    # maybe want to have things that are python defaults have custom search names? make it less dependent on language structure
                    next_step_data = recurse_data.__class__.__name__
                elif not hasattr(recurse_data, next_key):
                    return ["not"]
                else:
                    next_step_data = getattr(recurse_data, next_key)
                recurse_data = next_step_data
            else:
                # hit unrecursible type before finishing recursions
                return ["not"]
            should_skip_indexer = False

        return ["does"]

class MultiIndexer:
    '''class for tracking and updating secondary indices for entries'''
    def __init__(self, cache:"typing.Union[dict, Cache]"=None, input_secondary_indices=[]) -> None:
        self.cache = cache if cache is not None else {}
        '''cache also stands in for primary index'''
        self.is_cache_set = cache is not None
        self.is_cache_obj = issubclass(self.cache.__class__, Cache)
        self.secondary_indices:dict[str, AbstractIndex] = {}
        self.add_indices(*input_secondary_indices)
        if len(self.cache) > 0:
            self.reindex()

    def set_cache(self, cache:"typing.Union[dict, Cache]"):
        self.cache = cache
        self.is_cache_set = True
        self.is_cache_obj = issubclass(self.cache.__class__, Cache)
        self.reindex()

    def add_indices(self, *input_secondary_indices):
        for index in input_secondary_indices:
            if type(index) is str:
                # if string, assume name and build simplest most usable index
                index = FieldValueIndex(index, index)

            if not issubclass(type(index), AbstractIndex):
                cachev2_logger.warning(f"trying to add secondary index {index} but if of type that cache doesn't support")
                continue

            if index.name == "primary":
                cachev2_logger.warning("trying to add secondary index named 'primary' but that's a reserved name. skipping")
                continue
            if index.name in self.secondary_indices:
                cachev2_logger.warning(f"trying to add secondary index named {index.name} but that exists already. skipping")
                continue

            self.secondary_indices[index.name] = index

        self.reindex()

    def remove_indices(self, *index_names):
        for index_name in index_names:
            del self.secondary_indices[index_name]

    def get_keys(self, key, index_name="primary", default=None) -> typing.Any:
        '''same as the `get` method: returns a list of the entries in cache that fit the given key and index, but this returns the primary keys of these entries.
        Always returns found data as a list, if nothing found returns value passed in under default

        Parameters
        ---
        * key - `Any`
            key to use to find data
        * index_name - `str`
            name of index to search for key in, defaults to "primary" index
        * default - `Any`
            The value to return if key is not found, default value is None
        Returns
        ---
        If entries are found, returns a copy of a list of the one or more entries' primary keys.
        If no entries are found, returns the value of default'''
        if index_name == "primary" or index_name == "":
            cachev2_logger.debug(f"getting data from primary index")
            if key in self.cache:
                # don't want to format default value into a list so there's a filter
                # primary index assumed to have only one entry mapped, so format it as a list
                return [key]
            return default
        elif index_name not in self.secondary_indices.keys():
            cachev2_logger.debug(f"index <{index_name}> not found as a secondary index")
            # no point trying, invalid index
            return default
        else:
            cachev2_logger.debug(f"getting data from index <{index_name}>")
            primary_keys = self.secondary_indices[index_name].get(key, default=None)
            if primary_keys is None:
                return default
            return primary_keys
        
    def get(self, key, index_name="primary", default=None) -> typing.Any:
        '''same as the `get_keys` method: returns a list of the entries in cache that fit the given key and index, but this returns the entries' data itself.
        Always returns found data as a list, if nothing found returns value passed in under default. modifying objects directly may make indices stale, 
        try to use the indexer's set method.

        Parameters
        ---
        * key - `Any`
            key to use to find data
        * index_name - `str`
            name of index to search for key in, defaults to "primary" index
        * default - `Any`
            The value to return if key is not found, default value is None

        Return
        ---
        If entries are found, returns the data of the entries in a list. Copied using copy rules
        If no entries are found, returns the value of default
        '''
        cachev2_logger.debug(f"reporting, cache get passed key of <{key}> index of <{index_name}> default value of <{default}>")

        found_keys = self.get_keys(key=key, index_name=index_name, default=None)
        if found_keys is None:
            return default
        else:
            result_list = []
            for primary_key in found_keys:
                if primary_key in self.cache:
                    # does this need to be copied before putting in? might be overhead
                    result_item = self.cache.get(primary_key)
                    result_list.append(result_item)
                else:
                    # one of primary keys returned by index not actually stored, needs refresh
                    self.reindex(indices=[index_name])
                    return self.get(key=key, index_name=index_name, default=default)
            return result_list
        
    def get_ref(self, primary_key, default=None):
        '''returns the actual object stored. Modifying objects directly may make indices stale, 
        try to use the indexer's set method. '''
        if self.is_cache_obj:
            return self.cache.get_ref(primary_key, default)
        else:
            return self.cache[primary_key]
        
    def add_item(self, primary_key, item, or_overwrite=False):
        if primary_key in self.cache:
            if or_overwrite:
                return self.set_item(primary_key, item)
            return None
        
        if self.is_cache_obj:
            self.cache.add_item(primary_key, item)
        else:
            self.cache[primary_key] = item

        for index in self.secondary_indices.values():
            index.add_item(primary_key, item)
        return primary_key
    
    def add_items(self, entries:dict, or_overwrite=False):
        results = []
        for key, value in entries.items():
            result = self.add_item(key, value, or_overwrite=or_overwrite)
            results.append(result)
        return results
    
    def remove_item(self, primary_key):
        if primary_key not in self.cache:
            return None
        old_item = self.cache.get(primary_key, None)

        if self.is_cache_obj:
            self.cache.delete_item(primary_key)
        else:
            del self.cache[primary_key]

        for index in self.secondary_indices.values():
            index.remove_item(primary_key, old_item)
        
        return old_item

    def set_item(self, primary_key, item, all_old_keys = None):
        '''
        if in place edits are done to the object, must get a collection of keys before changes were made (just call `get_item_trackers` with same primary key) and pass that in `all_old_keys`. 
        No enforcement for it, system will behave in unexpected ways if not done that way'''
        if primary_key not in self.cache:
            return self.add_item(primary_key, item)
        # if in place changes, item and cache.get() will return the same object and data, so rely on old_keys parameter to know old state
        if all_old_keys is None:
            # if in place edits done and came here means bad state
            # if new data then this is what is supposed to happen. if caller passes in keys hope they called right function
            all_old_keys = self.get_item_trackers(primary_key)

        if self.is_cache_obj:
            self.cache.set_item(primary_key, item)
        else:
            self.cache[primary_key] = item

        for index in self.secondary_indices.values():
            index.set_item_keys(primary_key, all_old_keys[index.name], item)
        return primary_key

    def get_item_trackers(self, primary_key):
        '''get all indices' secondary keys for the item stored in cache'''
        item = self.cache.get(primary_key, None)
        if item is None:
            return None
        
        secondary_keys = {}
        for index in self.secondary_indices.values():
            secondary_keys[index.name] = index.get_item_secondary_keys(item)
        return secondary_keys
    
    def reindex(self, index_names:'typing.Optional[list[str]]' = None):
        '''reload all existing indices to point to items in the new cache'''
        if index_names is None or len(index_names) == 0:
            indices = self.secondary_indices.values()
        else:
            indices = []
            for index_name in index_names:
                if index_name != "primary":
                    indices.append(self.secondary_indices[index_name])

        for index in indices:
            index.clear()
            for key, item in self.cache.items():
                index.add_item(key, item)

    def clear(self):
        '''clear out all data in cache and indiex information'''
        self.cache.clear()
        for index in self.secondary_indices.values():
            index.clear()

    def __contains__(self, key):
        return key in self.cache
    
    def __len__(self):
        return len(self.cache)

class Cache:
    #note, this is a STUB
    def __init__(self) -> None:
        self.data = {}

    def add_item(self, primary_key, item):
        self.data[primary_key] = item

    def delete_item(self, primary_key):
        del self.data[primary_key]

    def set_item(self, primary_key, item):
        self.data[primary_key] = item

    def __contains__(self, key):
        return key in self.data
    
    def get(self, primary_key, default=None):
        return self.data.get(primary_key, default)
    
    def get_ref(self, primary_key, default=None):
        return self.data.get(primary_key, default)
    
    def clear(self):
        self.data.clear()

    def __iter__(self):
        return iter(self.data)
    
    def is_empty(self):
        return len(self.data) == 0
    
    def __len__(self):
        return len(self.data)
    
    def items(self):
        return self.data.items()
    
    def values(self):
        return self.data.values()
    
    def keys(self):
        return self.data.keys()