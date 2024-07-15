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

import src.utils.DotNotator as DotNotator

# TODO: Cache with cleaning included?
# TODO: adding without key specified? UUIDS?

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
    '''
    Template and parent class for custom secondary indices for MultiIndexer class to use. Custom index must be descendent of this class for MultiIndexer to use it.
    MultiIndexer informs Index of all changes to data. Indices are responsible for keeping secondary key mappings up to data with information it receives.
    All methods in this class are for MultiIndexer to call into and are missing implementation that needs to be filled in children, see doc strings and other documents for info.
    Indices removed from MultiIndex or never assigned to one will not update to changes in cache.
    
    Index should define and manage its own storage for mapping. It can store the actual object that is in cache, but is just expected to return primary keys that match the given secondary key.'''
    def __init__(self, name) -> None:
        self.name = name

    def get(self, key, default=None):
        '''returns list of primary keys for items that fit the given secondary key in this index, or the default value if no primary keys are found'''
        return default
    
    def clear(self):
        '''clear all data stored by index'''
        pass

    def get_item_secondary_keys(self, primary_key, item):
        '''find all secondary keys that this index would have for the given item. aka what secondary keys this index will map to item
        
        Returns
        ---
        list of secondary keys that this secondary index would use, or empty list if no keys
        '''
        return []

    def add_item(self, primary_key, item):
        '''callback when item has been added to data stores under given primary key and needs to be added to this index's tracking.'''
        pass

    def remove_item(self, primary_key, item):
        '''callback when item under given primary key has been removed from data stores and index tracking also needs to remove secondary keys. Takes item that was removed as Index object doesn't have 
        reference to cache to retrive that info'''
        pass

    def set_item_keys(self, primary_key, old_second_keys, item):
        '''callback when item under given primary key has had its internal data updated. 
        Index needs to be passed both the new data to find keys to be added, and old secondary keys to know what keys to remove since no other way to find data.'''
        pass

class FieldValueIndex(AbstractIndex):
    '''simple usable implementation of index. Uses calculations based on the values stored inside entries to create secondary key(s). 
    Allows a secondary key to map to multiple primary keys. For example: This is indexing a list of nodes that have a type field, this index can index by type so you can get a 
    list of all nodes that are type A vs type B.
    This class supports having multiple secondary keys for one primary key. For example: indexing nodes with a list of the names of actions, this can index by all action names so you can get
    a list of all nodes that use that action.
    This class takes a function as paramter keys_value_finder that finds the secondary keys for this index. Index expects it to take the item as parameter and return a list that will be used as secondary keys
    and for whoever provides it to do error handling. It should return either None or empty list if no keys for this index. If not provided it uses the `DotNotator` to find the calue of the field with the name 
    of the class'''
    def __init__(self, name, keys_value_finder=None) -> None:
        super().__init__(name)
        if keys_value_finder is None:
            keys_value_finder=lambda item: self.backup_value_finder(item)
        self.keys_value_finder = keys_value_finder
        '''function for grabbing secondary keys to track by. Index expects it to take the item as parameter and return a list and handle errors. None or empty list if no keys for this index'''
        self.pointers:dict[typing.Hashable, set[typing.Hashable]] = {}
        '''maps secondary key to set of primary keys that contain the secondary key as a value'''

    def get(self, key, default=None):
        value = self.pointers.get(key, None)
        if value is None:
            return default
        return list(value)
    
    def clear(self):
        self.pointers.clear()

    def _add_pointers(self, primary_key, secondary_keys):
        '''helper for this class. adds tracking information to mapping'''
        for secondary_key in secondary_keys:
            if secondary_key not in self.pointers:
                self.pointers[secondary_key] = set()
            self.pointers[secondary_key].add(primary_key)

    def _remove_pointers(self, primary_key, secondary_keys):
        '''helper for this class, removes tracking information'''
        for secondary_key in secondary_keys:
            if secondary_key in self.pointers and primary_key in self.pointers[secondary_key]:
                # prevent errors trying to remove something not in there
                self.pointers[secondary_key].remove(primary_key)
            if secondary_key in self.pointers and len(self.pointers[secondary_key]) < 1:
                del self.pointers[secondary_key]

    def add_item(self, primary_key, item):
        self._add_pointers(primary_key, self.get_item_secondary_keys(primary_key, item))

    def remove_item(self, primary_key, item):
        self._remove_pointers(primary_key, self.get_item_secondary_keys(primary_key, item))
    
    def set_item_keys(self, primary_key, old_second_keys, item):
        self._remove_pointers(primary_key, old_second_keys)
        self.add_item(primary_key, item)
    
    def get_item_secondary_keys(self, primary_key, item):
        value = self.keys_value_finder(item)
        if value is None:
            return []
        return copy.deepcopy(value)
    
    def backup_value_finder(self, item):
        '''default behavior for keys_value_finder - the function that finds list of secondary keys'''
        found_object = DotNotator.parse_dot_notation_string(self.name, item, custom_func_name="indexer")
        result_keys = set()

        if type(found_object) not in [dict, list, bool, str, int, float]:
            # found data is a complex object, probably some way to get keys but don't really have a default way so giving up. return blank
            return []
        elif isinstance(found_object, list):
            # uses list items as keys. only grabs hashable items, shouldn't have non-hashables inside anyways
            for item in found_object:
                try:
                    result_keys.add(copy.deepcopy(item))
                except:
                    pass
        elif isinstance(found_object, dict):
            # uses dict keys as keys. 
            for item in found_object.keys():
                result_keys.add(copy.deepcopy(item))
        else:
            # data is a bool, int, str etc. primitive type and hashable
            try:
                result_keys.add(found_object)
            except:
                pass
        return list(result_keys)
    
class ObjContainsFieldIndex(FieldValueIndex):
    '''another simple usable implementation of index. Indexes if certain fields or values exist inside entry.
    Only indexes by two values in that case, `does` and `not` for if contains field with a filled in non-null value'''
    def __init__(self, name, keys_value_finder) -> None:
        super().__init__(name, keys_value_finder)
        self.pointers["does"] = set()
        self.pointers["not"] = set()

    def get_item_secondary_keys(self, primary_key, item):
        value = self.keys_value_finder(item)
        if value is None:
            return ["not"]
        return ["does"]

class MultiIndexer:
    '''The main utility class this file is designed to add.
    Designed for tracking data objects where besides the key identifier(s), there also is a need to search or group by other 
    data field(s) or extrapolated properties of the stored objects. This class manages and tries to keep secondary indices in sync with primary.

    Object used for primary storage can be a dictionary or a subclass of Cache.
    It is important to use MultiIndexer's `add_item` `remove_item` and 'set_item` for adding removing or changing items respetively to keep secondary indices up to date
    with changes to items being stored. `reindex` helps if secondary indices are stale, and `get_all_secondary_keys` can be used when trying to set but have to do it on original object
    
    `MultiIndexer` keeps a primary mapping storage and secondary index objects. The built in functions for updating items in the cache automatically update secondary indices.
    When querying secondary indices, expects them to return primary indices not the objects themselves
    
    The cache implementation defines what to do with actual object data. Most especially whether to return copies or not.'''
    def __init__(self, cache:"typing.Optional[typing.Union[dict, Cache]]"=None, input_secondary_indices:"list[typing.Union[str, AbstractIndex]]"=None) -> None:
        '''
        Parameters
        ---
        * cache - `dict | Cache`
            Either a regular python dictionary or subclass of the Cache class defined in this file, defaults to dictionary. 
            MultiIndexer uses this as primary index and storage. Paased in object is given to MultiIndexer to manage, best not to
            change data stored outside of MultiIndexer's provided accessors. Unless cache object overrides the behavior, MultiIndexer
            get will return the object itself not a copy'''
        self.cache = cache if cache is not None else {}
        self.is_cache_obj = issubclass(self.cache.__class__, Cache)
        self.secondary_indices:dict[str, AbstractIndex] = {}

        if input_secondary_indices:
            self.add_indices(*input_secondary_indices)

    def set_cache(self, cache:"typing.Union[dict, Cache]"):
        '''
        tries to set the primary data cache MultiIndexer manages to the one passed in and reindexes. 
        Only makes changes if cache is not None. Old one is ignored by MultiIndexer.
        
        Returns
        ---
        `boolean` whether or not it set cache and made changes'''
        if cache is None:
            return False
        self.cache = cache
        self.is_cache_obj = issubclass(self.cache.__class__, Cache)
        # indices should be up to date with cache so need to clean up
        self.reindex()
        return True

    def add_indices(self, *input_secondary_indices):
        '''
        Adds the given indices passed in to the MultiIndexer object, then reindexes. Given indices are either created objects or a name of index with default behaviors.
        Cannot add indices that aren't subclasses of AbstractIndex, Index has name of primary, or repeated index; warns and ignores if it hits these cases'''
        added_index_names = []
        for index in input_secondary_indices:
            if type(index) is str:
                # if string, assume name and build simplest most usable index
                index = FieldValueIndex(index)

            if not issubclass(type(index), AbstractIndex):
                cachev2_logger.warning(f"trying to add secondary index {index} but is of type that cache doesn't support")
                continue

            if index.name == "primary":
                cachev2_logger.warning("trying to add secondary index named 'primary' but that's a reserved name. skipping")
                continue
            if index.name in self.secondary_indices:
                cachev2_logger.warning(f"trying to add secondary index named {index.name} but that exists already. skipping")
                continue
            added_index_names.append(index.name)
            self.secondary_indices[index.name] = index
        self.reindex(index_names=added_index_names)

    def remove_indices(self, *index_names):
        '''removes the indices with the given names from the MultiIndexer. Ignores if a name does not exist.'''
        for index_name in index_names:
            if index_name in self.secondary_indices:
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
            if primary_keys is None or primary_keys == []:
                return default
            return copy.deepcopy(primary_keys)

    def get(self, key, index_name="primary", default=None) -> typing.Any:
        '''same as the `get_keys` method: returns a list of the entries in cache that fit the given key and index, but this returns the entries' data itself.
        Always returns found data as a list, if nothing found returns value passed in under default. modifying objects directly may make indices stale, 
        try to use the indexer's `set` method.

        Parameters
        ---
        * key - `Any`
            key to use to find data, can be primary or secondary key
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

        # get all primary keys that fit the given index and key
        found_keys = self.get_keys(key=key, index_name=index_name, default=None)
        if found_keys is None:
            # didn't find key, got the default value back
            return default
        else:
            result_list = []
            for primary_key in found_keys:
                if primary_key in self.cache:
                    # get actual item or copy let cache decide
                    result_item = self.cache.get(primary_key)
                    result_list.append(result_item)
                else:
                    # one of primary keys returned by index not actually stored
                    if index_name == "primary" or index_name == "":
                        # if primary index, something's wrong. Key was found once and now not. guess return not found
                        return default
                    # is a primary key from a secondary key, needs refresh cause it means index desynced
                    self.reindex(indices=[index_name])
                    return self.get(key=key, index_name=index_name, default=default)
            return result_list
        
    def get_ref(self, primary_key, default=None):
        '''returns the actual object stored. Modifying objects directly may make indices stale, 
        try to use the indexer's set method instead of chaing object returned here. If still need to change, need to call `get_all_secondary_keys`
        on object before any updates, make updates, and pass secondary keys from before updates to set call'''
        if self.is_cache_obj:
            return self.cache.get_ref(primary_key, default)
        else:
            return self.cache[primary_key]
        
    def add_item(self, primary_key, item, or_overwrite=False):
        '''
        adds one item under the primary key into cache and updates indices. If primary key already exists must check overwriting is ok as well.

        Parameters
        ---
        * or_overwrite - `boolean`
            same as add_item or_overwrite, controls if it is ok to overwrite an existing item, in which it calls set

        Returns
        ---
        key of item just added or overwritten, none if it failed
        '''
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
        '''
        adds a bunch of entries into cache. check add_item for details on process

        Parameters
        ---
        * entries - `dict`
            all the entries to add to cache. each item's key becomes primary key in cache for the value
        * or_overwrite - `boolean`
            same as add_item or_overwrite, controls if it is ok to overwrite an existing item, in which it calls set
        
        Returns
        ---
        `array` A list of primary keys that were successfully added or overwritten
        '''
        results = []
        for key, value in entries.items():
            result = self.add_item(key, value, or_overwrite=or_overwrite)
            if result is not None:
                results.append(result)
        return results
    
    def remove_item(self, primary_key):
        '''
        removes an entry from cache and updates indices. Ignores if entry isn't inside cache
        
        Returns
        ---
        the item that was removed, or None if it wasn't found'''
        if primary_key not in self.cache:
            return None

        if self.is_cache_obj:
            old_item = self.cache.get_ref(primary_key, None)
            self.cache.remove_item(primary_key)
        else:
            old_item = self.cache.get(primary_key, None)
            del self.cache[primary_key]

        for index in self.secondary_indices.values():
            index.remove_item(primary_key, old_item)
        
        return old_item

    def set_item(self, primary_key, item, previous_secondary_keys=None):
        '''
        Sets or adds entry in cache under primary_key to the given item. Then tells indices to clean up keys (remove any old, add new changes). Uses previous_secondary_keys to know what keys were before edits
        and thus what needs to be removed from indices.
        Since MultiIndexer may return actual items stored in cache, data could be mistakenly edited in place without calling accessors provided and set can be called after these changes are made.
        Poses issue as now indices could be out of date of data in object.
        If working with in place edits outside of accessors, must get secondary keys before changes are made
        (just call `get_all_secondary_keys` with same primary key before changes) and pass that in `previous_secondary_keys`.
        No enforcement for it, system will return incorrect stale data if not done that way.
        The only other option provided is to reindex all indices.
        
        Returns
        ---
        returns key of item just set or added'''
        if primary_key not in self.cache:
            return self.add_item(primary_key, item)
        # if edits made on separate copy, item passed into set and cache.get() return different data, assume old is still inside cache and previous_secondary_keys is not necessary
        # if in place changes, item passed into set and cache.get() will return the same object and data, so are relying on privious_secondary_keys parameter to be filled so
        #       indices can know what keys to delete
        if previous_secondary_keys is None:
            # should only be in this if statement when edits made in separate copy (but not always, could still call get_all_secondary_keys and pass in)
            # if in place edits done and came here means in bad state
            previous_secondary_keys = self.get_all_secondary_keys(primary_key)

        if self.is_cache_obj:
            self.cache.set_item(primary_key, item)
        else:
            self.cache[primary_key] = item

        for index in self.secondary_indices.values():
            # assumes that if index name is ever missing, then it means no keys
            index.set_item_keys(primary_key, previous_secondary_keys[index.name] if index.name in previous_secondary_keys else [], item)
        return primary_key

    def get_all_secondary_keys(self, primary_key):
        '''
        get all indices' secondary keys for the item stored in cache under the given primary key
        
        Returns
        ---
        None if item isn't found, otherwise dictionary mapping secondary index name to keys that index uses for the item'''
        item = self.cache.get(primary_key, None)
        if item is None:
            return None
        
        secondary_keys = {}
        for index in self.secondary_indices.values():
            secondary_keys[index.name] = index.get_item_secondary_keys(primary_key, item)
        return secondary_keys
    
    def reindex(self, index_names:'typing.Optional[list[str]]'=None):
        '''
        reload indices to reflect current state of data stored by clearing them then updating with all current items. 
        Defaults to all indices, otherwise reloads just the list provided (if they are in indexer)
        
        Parameters
        ---
        * index_names - `Optional[list[str]]`
            list of index names to try and reindex'''
        if index_names is None or len(index_names) == 0:
            # default case
            indices = self.secondary_indices.values()
        else:
            # sort out indices named that are actually in self
            indices = []
            for index_name in index_names:
                if index_name != "primary" and index_name in self.secondary_indices:
                    indices.append(self.secondary_indices[index_name])

        for index in indices:
            index.clear()
            for key, item in self.cache.items():
                index.add_item(key, item)

    def clear(self):
        '''clear out all data in cache and index information'''
        self.cache.clear()
        for index in self.secondary_indices.values():
            index.clear()

    def __contains__(self, key):
        return key in self.cache
    
    def __len__(self):
        return len(self.cache)

class Cache:
    #note, this is a STUB
    '''wrapper class and Base class for MultiIndexer's cache. Meant to be storage so just wraps a dictionary, Inherit if there's more behavior primary cache needs compared to a dictionary.
    For example extra handlers for when items are added, more control over get returning copies or objects, seperate callbacks for adding new vs setting existing.'''
    def __init__(self) -> None:
        self.data = {}

    def add_item(self, primary_key, item):
        '''MultiIndexer uses this as callback to add new item to cache'''
        self.data[primary_key] = item

    def remove_item(self, primary_key):
        '''MultiIndexer uses this as callback to remove item from cache'''
        if primary_key in self.data:
            del self.data[primary_key]

    def set_item(self, primary_key, item):
        '''MultiIndexer uses this as callback to set existing item in cache to new data values'''
        self.data[primary_key] = item

    def __contains__(self, key):
        '''MultiIndexer does a lot of 'key in Cache' checks, needed for that behavior'''
        return key in self.data
    
    def get(self, primary_key, default=None):
        '''must work as a get item stored in Cache, can be overridden to return a copy of item'''
        return self.data.get(primary_key, default)
    
    def get_ref(self, primary_key, default=None):
        '''expected to work as a get item stored in cache, but always reference to actual object'''
        return self.data.get(primary_key, default)
    
    def clear(self):
        '''MultiIndexer expects this method to clear all existing data'''
        self.data.clear()

    def __iter__(self):
        return iter(self.data)
    
    def is_empty(self):
        return len(self.data) == 0
    
    def __len__(self):
        '''MultiIndexer has length override that calls this'''
        return len(self.data)
    
    def items(self):
        '''MultiIndexer uses this for looping'''
        return self.data.items()
    
    def values(self):
        '''MultiIndexer uses this for looping'''
        return self.data.values()
    
    def keys(self):
        '''MultiIndexer uses this for looping'''
        return self.data.keys()
   