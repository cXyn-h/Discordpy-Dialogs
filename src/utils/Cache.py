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

class COPY_RULES(Enum):
    ORIGINAL = 0
    SHALLOW = 1
    DEEP = 2
    ATTEMPT = 3

class UPDATE_STRAT(Enum):
    SET = 0
    ADD = 1
    DELETE = 2
    # if want to add fields, cache update can insert
    # nested lists want to add items to
    # want to remove from list
    # want to remove fields
    # update is pretty good at setting lists or other fields

class AbstractCacheEntry:
    DO_NOT_COPY_VARS = ["cache"]
    def __init__(self, primary_key, cache=None, timeout=180) -> None:
        self.primary_key = primary_key
        self.secondary_keys = {}
        self.cache = cache
        self.set_TTL(timeout_duration=timedelta(seconds=timeout))

    def set_TTL(self, timeout_duration:timedelta):
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

    def set_cache(self, cache:"typing.Union[Cache, None]"):
        self.cache = cache

    def reindex(self, index_names=None):
        if self.cache:
            self.cache.reindex(updated_keys=self.primary_key, index_names=index_names)

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        for variable, item in vars(self).items():
            if variable not in cls.DO_NOT_COPY_VARS and variable not in AbstractCacheEntry.DO_NOT_COPY_VARS:
                setattr(result, variable, copy.copy(item))
            else:
                setattr(result, variable, item)
        print(vars(result))
        return result
    
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for variable, item in vars(self).items():
            if variable not in cls.DO_NOT_COPY_VARS and variable not in AbstractCacheEntry.DO_NOT_COPY_VARS:
                setattr(result, variable, copy.deepcopy(item, memo))
            else:
                setattr(result, variable, item)
        print("in deepcopy method, result looks like", vars(result))
        return result
    
    def set(self, incoming):
        pass

    def update(self, incoming, field_update_strat):
        pass

class CacheEntry(AbstractCacheEntry):
    def __init__(self, primary_key, data, cache=None, timeout=180) -> None:
        super().__init__(primary_key, cache=cache, timeout=timeout)
        self.data = data

    def set(self, incoming):
        self.data.clear()
        self.data.update(incoming)

    def update(self, incoming, field_update_strat:UPDATE_STRAT):
        if id(incoming) == id(self.data):
            if field_update_strat == UPDATE_STRAT.DELETE:
                self.data.clear()
        else:
            if field_update_strat == UPDATE_STRAT.ADD:
                for update_key, update_data in incoming.items():
                    # update_data is all the items to update as key value pairs, so need to go through each one to see how it is changed
                    if update_key in self.data:
                        field_value = self.data.get(update_key)
                        if id(field_value) == id(update_data):
                            # same exact objects, already store same thing
                            continue
                        if type(field_value) is list:
                            if type(update_data) is list or type(update_data) is set:
                                # merge two collections. if you want to add a nested list, need to double wrap it
                                self.data[update_key].extend(update_data)
                            elif type(update_data) is not dict and update_data is not None:
                                # not going to support trying to add dictionary items from list, might be confusing if accepting keys or values
                                # otherwise catches things assumed are single objects/values
                                self.data[update_key].append(update_data)
                        elif type(field_value) is dict:
                            if type(update_data) is dict:
                                self.data[update_key].update(update_data)
                        elif type(field_value) is set:
                            if type(update_data) is set or type(update_data) is list:
                                for update_data_entry in list(update_data):
                                    if isinstance(update_data_entry, typing.Hashable):
                                        self.data[update_key].add(update_data_entry)
                            elif isinstance(update_data, typing.Hashable) and update_data is not None:
                                self.data[update_key].add(update_data)
                        elif field_value is None:
                            self.data[update_key] = update_data
                        elif update_data is not None:
                            self.data[update_key] = update_data
                    else:
                        self.data[update_key] = update_data
            elif field_update_strat == UPDATE_STRAT.SET:
                cachev2_logger.info(f"{type(self)} {type(incoming)}")
                self.data.update(incoming)
            else:
                # note for this else statement: field_update_strat == UPDATE_STRAT.DELETE
                for update_key, update_data in incoming.items():
                    if update_key in self.data:
                        field_value = self.data.get(update_key)
                        if type(field_value) is list or type(field_value) is set:
                            # updating an existing entry that is a lsit or set, next is how to update based on passed in data
                            if update_data is None:
                                # yes delete the list entry itself. this is what happens with primitive type fields, wanted some way to do it
                                # for lists too
                                del self.data[update_key]
                            elif id(field_value) == id(update_data):
                                # just in case. passed and and stored being same exact object would cause havok for deletes
                                field_value.clear()
                            elif type(update_data) is list or type(update_data) is set:
                                for nested_key in update_data:
                                    if nested_key in self.data.get(update_key):
                                        self.data.get(update_key).remove(nested_key)
                            elif type(update_data) is not dict:
                                # not going to support trying to delete dictionary items from list, might be confusing if accepting keys or values
                                # otherwise this catches things that we assume are single objects/values so only one thing to remove
                                if update_data in self.data.get(update_key):
                                    self.data.get(update_key).remove(update_data)
                        elif type(field_value) is dict:
                            # updating an existing entry that is a dict, next is how to update based on passed in data
                            if update_data is None:
                                del self.data[update_key]
                            elif id(field_value) == id(update_data):
                                field_value.clear()
                            elif type(update_data) is list or type(update_data) is set or type(update_data) is dict:
                                # for all of these, treat as group of keys want to delete from dict
                                for nested_key in update_data:
                                    if isinstance(nested_key, typing.Hashable) and nested_key in self.data.get(update_key):
                                        del self.data.get(update_key)[nested_key]
                            elif isinstance(update_data, typing.Hashable) and update_data in field_value:
                                # case for everything else, treat as single item to remove from dict
                                del self.data.get(update_key)[update_data]
                        else:
                            del self.data[update_key]

class AbstractIndex:
    def __init__(self, name) -> None:
        self.name = name
        self.pointers:dict[typing.Hashable, set[typing.Hashable]] = {}
        self.cache = None

    def set_cache(self, cache:"Cache"):
        '''sets the cache this index is connected to and all data is in reference to'''
        self.cache = cache
        self.pointers.clear()
        if not cache.is_empty():
            for key, entry in cache:
                self.add_entry(entry)

    def add_pointer(self, primary_key, secondary_key):
        '''helper that records index information. If secondary_key type can be hashed, index will use it to point to primary_key'''
        if isinstance(secondary_key, typing.Hashable):
            if secondary_key not in self.pointers:
                self.pointers[secondary_key] = set()
            self.pointers[secondary_key].add(primary_key)

    def del_pointer(self, primary_key, secondary_key):
        '''helper that removes index information.'''
        if isinstance(secondary_key, typing.Hashable) and secondary_key in self.pointers:
            self.pointers[secondary_key].remove(primary_key)
            if len(self.pointers[secondary_key]) == 0:
                del self.pointers[secondary_key]

    def reindex(self, updated_keys:'typing.Union[list[str], None]'=None):
        if not self.cache:
            # only passed keys currently because want to match function signiture with cache's to make it less confusing, but this makes it dependent on linked cache
            # so early check and break if its impossible to do
            return
        if updated_keys is None:
            # assuming want to renew everything
            updated_keys = [key for key, _ in self.cache]
        cachev2_logger.info(f"doing reindex for index {self.name}, keys {updated_keys}")

        for pk in updated_keys:
            if pk not in self.cache:
                # fail safe to make sure things are ok
                cachev2_logger.debug(f"found item {pk} not in cache")
                continue
            entry = self.cache.get(pk, index_name='primary', override_copy_rule=COPY_RULES.ORIGINAL)[0]
            cachev2_logger.info(f"item {pk} in cache, data is currently {entry.data}")
            try:
                # using the entry object to record what secondary keys were used, since indices are responsible for the
                #   keys used, it doubles as a record of what the keys were last time any official-update-function
                #   updated data
                previous_keys = entry.secondary_keys.get(self.name, [])
            except Exception as e:
                # failsafe for duck typed entries
                previous_keys = []
            current_keys = self.parse_for_keys(entry)
            if previous_keys == []:
                cachev2_logger.debug(f"emergency cleanup of index {self.name}")
                # assuming something really wrong or index just decides to use clear capability
                self.emergency_cleanup(delete_pks=[pk])
            if current_keys != previous_keys:
                cachev2_logger.debug(f"reindexing item {pk} for index {self.name}")
                # mismatch means index out of date, renew index records and object records
                for prev_key in previous_keys:
                    self.del_pointer(pk, prev_key)
                for current_key in current_keys:
                    self.add_pointer(pk, current_key)
                try:
                    entry.secondary_keys.update({self.name: current_keys})
                except Exception as e:
                    pass

    def emergency_cleanup(self, delete_pks = None):
        '''check all recorded clean up any references to any key in the passed in list'''
        if delete_pks is None:
            self.pointers.clear()
            return
        for pk in delete_pks:
            for k, pk_list in list(self.pointers.items()):
                if pk in pk_list:
                    self.pointers[k].remove(pk)
                if len(pk_list) == 0:
                    del self.pointers[k]

    def iter(self, key):
        '''creates and returns an interator through all primary keys of entries that fall under given key in this index'''
        return iter(self.pointers.get(key, set()))   

    def __len__(self):
        return len(self.pointers) 

    def get(self, key, default=None):
        '''index retrive primary keys that fit the given key in this index'''
        return self.pointers.get(key, default)

    def parse_for_keys(self, entry:AbstractCacheEntry):
        '''method for getting what this index would use for keys for the given object'''
        return []    

    def add_entry(self, entry:AbstractCacheEntry):
        '''index callback when entry is added to cache or index. Must implement in child classes. Cache itself will only call this
         when inserting a new key value pair. Meant for indices to sort out if entry should be indexed and with what value'''
        pass

    def update_entry(self, entry:AbstractCacheEntry):
        '''index callback when an entry that exists in the cache is updated. Must implement in child classes. Meant for checking
        if the values that define this index were changed or not and assigning a different place'''
        pass

    def set_entry(self, entry:AbstractCacheEntry):
        '''index callback when an entry that exists in the cache has all its data set to new stuff. Must implement in child classes.
        Meant for checking if the values that define this index were changed or not and assigning a different place'''
        pass

    def del_entry(self, entry:AbstractCacheEntry):
        '''index callback when an entry is deleted from cache. Must implement in child classes. Mean for removing items from reference and
        cleaning up any now-hanging index structure'''
        pass  

class SimpleIndex(AbstractIndex):
    '''index that works on columns of hashable values stored in cache'''
    def __init__(self, name, col_name) -> None:
        super().__init__(name)
        self.col_name = col_name

    def parse_for_keys(self, entry):
        '''SimpleIndex key is just the value at the index's selected column'''
        if hasattr(entry, "data"):
            if self.col_name in entry.data and isinstance(entry.data[self.col_name], typing.Hashable):
                return [entry.data[self.col_name]]
            else:
                return []
        return []

    def add_entry(self, entry: AbstractCacheEntry):
        keys = self.parse_for_keys(entry)
        for k in keys:
            self.add_pointer(entry.primary_key, k)
        entry.secondary_keys[self.name] = keys
    
    def update_entry(self, entry: AbstractCacheEntry):
        self.reindex(updated_keys=[entry.primary_key])

    def set_entry(self, entry: AbstractCacheEntry):
        self.reindex(updated_keys=[entry.primary_key])

    def del_entry(self, entry: AbstractCacheEntry):
        previous_keys = entry.secondary_keys.get(self.name, [])
        for prev_key in previous_keys:
            self.del_pointer(entry.primary_key, prev_key)

class CollectionIndex(SimpleIndex):
    '''define this index on a col_name to auto idex anything updated or added to linked cache based on the value for col_name.
    This one can work on hashable types, lists and sets filled with hashable types, and dictionaries. Indexes the container structures by indexing each item or first level key inside.
    It technically can handle dictionaries nested in data, but it would be better to flatten the nesting.

    eg. if data has `col_name: list(1,2,3)` a get on index with key of 1 will return this entry.
    if data has `col_name: {"extras":"extra data", "another_object":{...}}` then get on index can find this entry with keys of "extras" or "another_object"

    Can also handle a mix where sometimes the field in data can have primirtive times
    and others is a list.
    eg. entry one has `col_name: list(1,2,3)`, entry two has `col_name: 3` and both can be found with a get on this index with key 3
    '''
    def __init__(self, name, col_name) -> None:
        super().__init__(name, col_name)

    def parse_for_keys(self, entry):
        '''CollectionIndex key is just the value at the index's selected column'''
        if hasattr(entry, "data"):
            if self.col_name in entry.data:
                col_data = entry.data[self.col_name]
                if type(col_data) is set or type(col_data) is list:
                    return [data_entry for data_entry in col_data if isinstance(data_entry, typing.Hashable)]
                elif type(col_data) is dict:
                    return [data_entry for data_entry in col_data.keys() if isinstance(data_entry, typing.Hashable)]
                return [entry.data[self.col_name]]
            else:
                return []
        return []

class Cache:
    '''
    assumes primary key only has one object associated with it
    '''
    # get and delete (maybe others too) based on multiple keys??
    def __init__(self, input_secondary_indices = [], defualt_get_copy_rule = COPY_RULES.ORIGINAL, default_timeout=180) -> None:
        '''
        Parameters
        ---
        * secondaryIndices - `list[Union[str, Index]]`
            list of indices to attach to this cache. if a string, creates a SimpleIndex that indexes based off of column of data with same name as index.
            Otherwise should be a child of Index class, and the object gets added to cache so it receives callbacks for any changes to cache entries.
        * copy_rules - `COPY_RULES`
            defines if returned values are actual or copies of data in cache, and how to copy. COPY_RULES Enum has values: shallow, deep, None, attempt.
        * default_timeout - `int`
            default amount of seconds to keep things in the cache if cleaning is on
        '''

        self.secondary_indices:dict[str, AbstractIndex] = {}
        '''dict of index objects providing other ways to find objects'''
        self.default_get_copy_rule = defualt_get_copy_rule
        self.data:dict[typing.Any, AbstractCacheEntry] = {}
        '''the actual dictionary storing data, primary key to data'''
        self.default_timeout = default_timeout

        self.cleaning_task = None
        self.cleaning_status = {"state":CLEANING_STATE.STOPPED, "next": None, "now": None}
        self.add_indices(input_secondary_indices)

    def add_indices(self, input_secondary_indices=[]):
        for index in input_secondary_indices:
            if type(index) is str:
                # if string, assume name and build simplest most usable index
                index = SimpleIndex(index, index)

            if not issubclass(type(index), AbstractIndex):
                cachev2_logger.warning(f"trying to add secondary index {index} but if of type that cache doesn't support")
                continue

            if index.name == "primary":
                cachev2_logger.warning("trying to add secondary index named 'primary' butthat's a reserved name . skipping")
                continue
            if index.name in self.secondary_indices:
                cachev2_logger.warning(f"trying to add secondary index named {index.name} but that exists already. skipping")
                continue

            self.secondary_indices[index.name] = index
            index.set_cache(self)

    def apply_copy_rule(self, cache_data, override_copy_rule=None):
        '''
        checks and applies if cache needs to return copies of its data. can override the cache's default setting by passing in a rule

        Parameters
        ---
        * cache_data - `Any`
            the data to be copied (or not)
        * temp_copy_rule - `COPY_RULES`
            override to default copy strategy for how to copy that only applies on this call

        Return
        ---
        a copy or the object passed in as cache_data depending on cache's copy rules overridden by given override
        '''
        if override_copy_rule is None:
            override_copy_rule = self.default_get_copy_rule

        if override_copy_rule == COPY_RULES.DEEP:
            return copy.deepcopy(cache_data)
        elif override_copy_rule == COPY_RULES.SHALLOW:
            return copy.copy(cache_data)
        elif override_copy_rule == COPY_RULES.ATTEMPT:
            try:
                return copy.deepcopy(cache_data)
            except Exception:
                try:
                    return copy.copy(cache_data)
                except Exception:
                    return cache_data
        else:
            return cache_data

    def get_key(self, key, index_name="primary", default=None) -> typing.Any:
        '''same as the get method: returns a list of the entries in cache that fit the given key and index, but this returns the primary keys of these entries.
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
            if key in self.data:
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
            primary_keys = self.secondary_indices[index_name].get(key, default)
            if primary_keys == default:
                return default
            return list(primary_keys)

    def get(self, key, index_name="primary", default=None, override_copy_rule=None) -> typing.Any:
        '''same as the get_key method: returns a list of the entries in cache that fit the given key and index, but this returns the entries' data itself.
        Always returns found data as a list, if nothing found returns value passed in under default

        Parameters
        ---
        * key - `Any`
            key to use to find data
        * index_name - `str`
            name of index to search for key in, defaults to "primary" index
        * default - `Any`
            The value to return if key is not found, default value is None
        * override_copy_rule - `COPY_RULES`
            The override for what type of copy or reference to get from cache for this run of get.

        Return
        ---
        If entries are found, returns the data of the entries in a list. Copied using copy rules
        If no entries are found, returns the value of default
        '''
        cachev2_logger.debug(f"reporting, cache get passed key of <{key}> index of <{index_name}> default value of <{default}>")

        result = self.get_key(key=key,index_name=index_name, default=default)
        if result == default:
            return default
        else:
            return [self.apply_copy_rule(self.data.get(primary_key), override_copy_rule=override_copy_rule) for primary_key in result]

    def add(self, key=None, value=None, or_overwrite=False, addition_copy_rule=COPY_RULES.SHALLOW):
        ''' adds or overwrites cache entry at given primary key with given value

        Parameters
        ---
        * key - `Any`
            the primary key to add the item under, defaults to uuid version 4 in hexdecimal
        * value - `dict[Any, Any]`
            the data to store under this key, defaults to empty dictionary
        * or_overwrite - `bool`
            if overwritting existing data is ok, defaults to false
        * addition_copy_rule - `COPY_RULES`
            rule for how to copy incoming data before storing. defaults to shallow copy

        Return
        ---
        all things are stored as CacheEntry objects (there's some management data) with a data dictionary so return is a CacheEntry
        object that was just added or None if it couldn't add anything'''
        if key is None and value is None:
            #this is pointless
            return None
        if key is None:
            #note: not sure if this generates IDs in a way that is same for multithreading or multiprocessing. It should? Documentation doesn't say it isn't either
            key = uuid.uuid4().hex
        if value is None:
            value = {}

        cachev2_logger.debug(f"adding data to cache, key: <{key}>, value <{value}>")
        if key in self.data:
            if not or_overwrite:
                # if key is recorded and not allowed to overwrite, then can't do anything
                return None
            # allowed to overwrite previous data, so technically a set rather than an add
            cachev2_logger.info("debugging, add is adding something that already exists, going to set")
            return self.set(key=key, value=value, index_name='primary', addition_copy_rule=addition_copy_rule)
        else:
            to_add = value
            if addition_copy_rule == COPY_RULES.SHALLOW:
                to_add = copy.copy(value)
            elif addition_copy_rule == COPY_RULES.DEEP:
                to_add = copy.deepcopy(value)
            elif addition_copy_rule == COPY_RULES.ATTEMPT:
                try:
                    to_add = copy.deepcopy(value)
                except Exception:
                    to_add = copy.copy(value)

            if type(to_add) is dict:
                self.data[key] = CacheEntry(key, to_add, cache=self, timeout=self.default_timeout)
            else:
                self.data[key] = to_add
                self.data[key].set_cache(self)

            for index in self.secondary_indices.values():
                index.add_entry(self.data[key])

        return self.data[key]

    def add_all(self, entries:dict, or_overwrite=False, addition_copy_rule=COPY_RULES.SHALLOW):
        '''add multiple entries into the cache

        Parameters
        ---
        * entries - `dict[Any, dict[Any, Any]]`
            all the entries, formatted as mapping of primary key to data for that primary key.

        Return
        ---
        dictionary mapping of key to either a CacheEntry if added or None
        '''
        results = {}
        for key, value in entries.items():
            result = self.add(key, value, or_overwrite=or_overwrite, addition_copy_rule=addition_copy_rule)
            results[key] = result
        return results

    def update(self, key, value, index_name="primary", addition_copy_rule=COPY_RULES.SHALLOW, or_create=True, field_update_strat=UPDATE_STRAT.ADD):
        '''
        updates the stored data and indices at given index and key. Uses the given value dictionary and field_update_strat to know what fields and how to update. Field_update_strat is how to modify elements
        of sets lists or first level of dictionaries. ie there's a list of string in data, can pass in two new values with update strat of ADD to add those two elements, SET to set to list with only those two items,
        DELETE to remove those two elements if they are in list. Uses the given copy rule for if copying of incoming value is needed

        Parameters
        ---
        * key - `Any`
            key to use to find data
        * value - `dict[Any, Any]`
            the data to store under this key
        * index_name - `str`
            name of index to search for key in, defaults to "primary" index
        * or_create - `bool`
            if ok to create entry if not found. creates with given key if using primary index otherwise uses randomized uuid. defaults to True
        * addition_copy_rule - `COPY_RULES`
            rule for how to copy incoming data before storing. defaults to shallow copy
        * field_update_strat - `UPDATE_STRAT`
            rule for how to update nested structures with passed in data

        Return
        ---
        If primary or nonexistant index was used and something was updated or added, the single up-to-date CacheEntry object.
        If a secondary index was used, a dictionary of primary keys that were
        updated or added to the up-to-date CacheEntry objects. None otherwise if nothing was updated
        '''
        # for testing this setting
        # field_update_strat=UPDATE_STRAT.SET
        # recusrive function, only primary key option really adds data, if by secondary it calls again with primary key
        if index_name == "primary" or index_name == "":
            if key in self.data:
                # key already saved in cache
                to_update = value
                if addition_copy_rule == COPY_RULES.SHALLOW:
                    to_update = copy.copy(value)
                elif addition_copy_rule == COPY_RULES.DEEP:
                    to_update = copy.deepcopy(value)
                elif addition_copy_rule == COPY_RULES.ATTEMPT:
                    try:
                        to_update = copy.deepcopy(value)
                    except Exception:
                        to_update = copy.copy(value)

                # actual update of data
                self.data.get(key).update(to_update, field_update_strat=field_update_strat)
                for index in self.secondary_indices.values():
                        index.update_entry(self.data.get(key))
                # timeout is based on last change
                self.data.get(key).set_TTL(timedelta(seconds=self.default_timeout))
                self.notify_soonest_cleaning(self.data.get(key).timeout)
                return self.data.get(key)
            else:
                # primary key not found
                if or_create:
                    self.add(key, value, addition_copy_rule=addition_copy_rule)
                    return self.data.get(key)
                return None
        elif index_name in self.secondary_indices.keys():
            results = {}
            primary_keys = self.get_key(key=key,index_name=index_name, default=set())
            for pk in list(primary_keys):
                # if no second process or async changes, then or_create can't affect anything while executing for loop. never hits that condition
                update_res = self.update(pk, value, index_name="primary")
                results[pk] = update_res
            if len(primary_keys) == 0 and or_create:
                # length of zero means nothing found, which is when or_create should be checked
                entry = self.add(value=value, addition_copy_rule=addition_copy_rule)
                results[entry.primary_key] = entry
            return results
        else:
            # index does not exist
            if or_create:
                entry = self.add(value=value, addition_copy_rule=addition_copy_rule)
                return entry
            return None

    def set(self, key, value, index_name="primary", addition_copy_rule = COPY_RULES.SHALLOW, or_create=True):
        if index_name == "primary" or index_name == "":
            if key in self.data:
                to_update = value
                if addition_copy_rule == COPY_RULES.SHALLOW:
                    to_update = copy.copy(value)
                elif addition_copy_rule == COPY_RULES.DEEP:
                    to_update = copy.deepcopy(value)
                elif addition_copy_rule == COPY_RULES.ATTEMPT:
                    try:
                        to_update = copy.deepcopy(value)
                    except Exception:
                        to_update = copy.copy(value)
                
                if id(value) != id(self.data.get(key).data):
                    self.data[key].set(to_update)
                self.data.get(key).set_TTL(timedelta(seconds=self.default_timeout))
                for index in self.secondary_indices.values():
                    index.set_entry(self.data.get(key))
                self.notify_soonest_cleaning(self.data.get(key).timeout)
                return self.data.get(key)
            else:
                if or_create:
                    self.add(key, value, addition_copy_rule=addition_copy_rule)
                    return self.data.get(key)
                return None
        elif index_name in self.secondary_indices.keys():
            results = {}
            primary_keys = self.get_key(key=key,index_name=index_name, default=set())
            for pk in list(primary_keys):
                update_res = self.set(pk, value, index_name="primary")
                results[pk] = update_res
            if len(primary_keys) == 0 and or_create:
                # length of zero means nothing found
                entry = self.add(value=value, addition_copy_rule=addition_copy_rule)
                results[entry.primary_key] = entry
            return results
        else:
            if or_create:
                entry = self.add(value=value, addition_copy_rule=addition_copy_rule)
                return entry
            return None

    def delete(self, key, index_name="primary"):
        if index_name == "primary" or index_name == "":
            if key in self.data:
                cachev2_logger.debug(f"deleting key <{key}>")
                value = self.data.get(key)
                for index in self.secondary_indices.values():
                    index.del_entry(value)
                value.set_cache(None)
                del self.data[key]
        elif index_name in self.secondary_indices.keys():
            # cachev2_logger.debug(f"deleting key <{key}> in index <{index_name}>")
            primary_keys = self.get_key(key=key,index_name=index_name, default=set())
            for pk in list(primary_keys):
                self.delete(pk, index_name="primary")

    def search(self, search_filters:dict, override_copy_rule=None):
        result = []
        for pk, entry in self.data.items():
            filter_pass = True
            for filter_key, filter_val in search_filters.items():
                if filter_key not in entry.data or entry.data[filter_key] != filter_val:
                    filter_pass = False
                    break
            if filter_pass:
                result.append(self.apply_copy_rule(entry.data, override_copy_rule))
        return result

        #TODO: WIP, how to do ands and ors

    def reindex(self, updated_keys:'typing.Union[str, list[str], None]'=None, index_names:'typing.Union[str, list[str], None]' = None):
        if updated_keys is None:
            updated_keys = list(self.data.keys())
        if type(updated_keys) is not list:
            updated_keys = [updated_keys]

        if index_names is None:
            index_names = list(self.secondary_indices.keys())
        if type(index_names) is not list:
            index_names = [index_names]

        # making sure indices exist good as prep step before reindex calls because index is nested loop 
        for index_name in list(index_names):
            if index_name not in self.secondary_indices:
                index_names.remove(index_name)

        for key in updated_keys:
            if key not in self.data:
                continue
            for index_name in index_names:
                index = self.secondary_indices[index_name]
                index.reindex(updated_keys=[key])

    def clear(self):
        for pk in list(self.data.keys()):
            self.delete(pk, index_name="primary")

    def __contains__(self, key):
        return key in self.data.keys()

    def is_empty(self):
        return len(self.data) == 0

    def __iter__(self):
        return iter(self.data.items())

    def iter(self, key, index_name="primary"):
        if index_name == "primary" or index_name == "":
            if key in self.data:
                return iter([self.data.get(key)])
            return iter([])
        elif index_name not in self.secondary_indices.keys():
            return iter([])
        else:
            return iter(self.get(key, index_name=index_name))

    def __len__(self):
        return len(self.data)

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    # NOTE: This task is not built for canceling. canceling can cause stopping in middle of custom cleanup methods, no tracking currently to prevent double calls to methods.
    async def clean_task(self, delay:float):
        this_cleaning = asyncio.current_task()
        cleaning_logger.info(f"clean task id <{id(this_cleaning)}><{this_cleaning}> starting, initial delay is <{delay}>")
        await asyncio.sleep(delay)
        cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> initial sleep done, checking if looping. current status {self.cleaning_status} and task {this_cleaning}")
        while self.cleaning_status["state"] in [CLEANING_STATE.STARTING, CLEANING_STATE.RUNNING]:
            cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> is going through a loop current state {self.cleaning_status}")
            if this_cleaning == self.cleaning_task:
                self.cleaning_status["state"] = CLEANING_STATE.RUNNING
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> inital startup changed state to running {self.cleaning_status}")
            starttime = datetime.utcnow()

            cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> getting timed out items. current state {self.cleaning_status}")
            timed_out_entries, next_time = self.get_timed_out_info()
            if this_cleaning == self.cleaning_task:
                self.cleaning_status["now"] = self.cleaning_status["next"]
                self.cleaning_status["next"] = next_time
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> changed next time state {self.cleaning_status}")

            if next_time is None:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found time for next clean is none, no further cleaning possible current state {self.cleaning_status}")
            else:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found next round is at {next_time}, {(next_time - starttime).total_seconds()} from now")
            try:
                cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> doing actual node pruning current state {self.cleaning_status}")
                self.clean(timed_out_entries, next_time=next_time, this_cleaning=this_cleaning)
            except Exception as e:
                # last stop catch for exceptions just in case, otherwise will not be caught and aysncio will complain of unhandled exceptions
                if this_cleaning == self.cleaning_task:
                    cleaning_logger.warning(f"handler id {id(self)} cleaning task id <{id(this_cleaning)}> at time {starttime} failed. details: {type(e)} {e}")
                    self.cleaning_status["state"] = CLEANING_STATE.STOPPED
                    self.cleaning_status["now"] = None
                    self.cleaning_status["next"] = None
                    cleaning_logger.warning(f"cleaning task id <{id(this_cleaning)}> at failure changed state to stopped {self.cleaning_status}")
                return

            # the task executing at this point may be one in handler or old one that started but ran over time but stayed running to make sure
            # nodes it found are cleaned
            if self.cleaning_status["state"] in [CLEANING_STATE.STOPPING, CLEANING_STATE.STOPPED]:
                # if cleaning is trying to stop, don't really want to loop for another clean. doesn't matter which task. so go to wrap up section
                break
            elif this_cleaning == self.cleaning_task:
                # only want to consider looping on main task, other ones are are only meant to finish current clean to make sure nodes are cleaned up
                #       in case the task restarts can't get to them
                if next_time is None:
                    # cleans not needed currently so mark it differently from stopped to know its ok to auto start them up again
                    cleaning_logger.debug(f"cleaning task id <{id(this_cleaning)}> found time for next clean is none, no further cleaning possible current state {self.cleaning_status}")
                    self.cleaning_status["state"] = CLEANING_STATE.PAUSED
                    self.cleaning_status["now"] = None
                    self.cleaning_status["next"] = None
                    return

                next_sleep_secs = max(0, (next_time - datetime.utcnow()).total_seconds())
                cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> last step of one round of cleaning, setting sleep time and waiting. status is {self.cleaning_status}, duration is {next_sleep_secs}")
                await asyncio.sleep(next_sleep_secs)
            else:
                # if not main task only wanted to finish clean, so go to wrap up section, technically could exit just here
                break

        #after loops wrap up section. updating status if supposed to
        cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> finished loops current state {self.cleaning_status}")
        if this_cleaning == self.cleaning_task:
            self.cleaning_status["state"] = CLEANING_STATE.STOPPED
            self.cleaning_status["now"] = None
            self.cleaning_status["next"] = None
            cleaning_logger.debug(f"clean task id <{id(this_cleaning)}> end of task changed state to stopped {self.cleaning_status}")


    def notify_soonest_cleaning(self, new_time:datetime):
        if self.cleaning_status["state"] in [CLEANING_STATE.STOPPED, CLEANING_STATE.STOPPING] or new_time is None:
            return
        if self.cleaning_status["next"] is None or new_time < self.cleaning_status["next"]:
            self.stop_cleaning()
            self.start_cleaning()

    def get_timed_out_info(self) -> 'tuple[list[str],typing.Union[datetime,None]]':
        now = datetime.utcnow()
        # TODO: future performance upgrade: all this sorting can probably be skipped with a min-heap structure. at this point too lazy to implement
        next_soonest_timestamp = None
        timed_out_entries = []
        for primary_key, cache_entry in self.data.items():
            # every node will have timeout, it might be valid teime or a None
            if cache_entry.timeout is not None:
                if cache_entry.timeout <= now:
                    cleaning_logger.debug(f"found cache entry <{primary_key}> has timed out")
                    timed_out_entries.append(primary_key)
                else:
                    if next_soonest_timestamp is None or cache_entry.timeout < next_soonest_timestamp:
                        next_soonest_timestamp = cache_entry.timeout
        return timed_out_entries, next_soonest_timestamp


    #NOTE: FOR CLEANING ALWAYS BE ON CAUTIOUS SIDE AND DO TRY EXCEPTS ESPECIALLY FOR CUSTOM HANDLING. maybe should throw out some data if that happens?
    def clean(self, timed_out_entries:"list[str]", next_time:typing.Union[datetime,None]=None, this_cleaning:typing.Union[asyncio.Task,None]=None):
        cleaning_logger.debug("doing cleaning action. handler id <%s> task id <%s>", id(self), id(asyncio.current_task()) if asyncio.current_task() else "N/A")
        # clean out old data from internal stores
        #TODO: more defenses and handling for exceptions
        for entry_key in timed_out_entries:
            # assuming if not active, some clean task busy cleaning. hopefully doesn't mess anything up
            if entry_key in self.data:
                del self.data[entry_key]

    def start_cleaning(self, event_loop:asyncio.AbstractEventLoop=None):
        event_loop = asyncio.get_event_loop() if event_loop is None else event_loop
        'method to get the repeating cleaning task to start'
        if self.cleaning_status["state"] in [CLEANING_STATE.RUNNING, CLEANING_STATE.STARTING]:
            return False
        self.cleaning_task = event_loop.create_task(self.clean_task(delay=0))
        self.cleaning_status["state"] = CLEANING_STATE.STARTING
        self.cleaning_status["next"] = datetime.utcnow()
        cleaning_logger.info(f"starting cleaning. handler id <{id(self)}> task id <{id(self.cleaning_task)}>, <{self.cleaning_task}>")
        return True


    def stop_cleaning(self):
        cleaning_logger.info("stopping cleaning. handler id <%s> task id <%s>", id(self), id(self.cleaning_task))
        if self.cleaning_status["state"] in [CLEANING_STATE.STOPPING, CLEANING_STATE.STOPPED]:
            return False
        # res = self.cleaning_task.cancel()
        # cleaning_logger.debug(f"result from canceling attempt, {res}")
        self.cleaning_status["state"] = CLEANING_STATE.STOPPING
        cleaning_logger.debug(f"end of handler stopping method status {self.cleaning_status}, {self.cleaning_task}")
        return True