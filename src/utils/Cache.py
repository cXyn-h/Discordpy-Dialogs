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

class SLEEPER_STATE(Enum):
    STARTING=1
    CLEANING=2
    SLEEPING=3
    HIBERNATING=4
    STOPPING=5
    STOPPED=6

# class SleeperTask:
#     #TODO: WIP, maybe change enum to this file's enum. generalization needed, looking at idea if hibernating works
#     # don't know if want clean method passed in or passing in lists to clean and this has all logic for checking timeouts
#     '''Task that runs as little as possible. variable time between run cycles and goes into deeper waiting when there's nothing new'''
#     def __init__(self, callback:typing.Coroutine, event_loop:asyncio.AbstractEventLoop=None) -> None:
#         self.callback = callback
#         self.task = None
#         self.status = CLEANING_STATE.STOPPED
#         self.current_run = None
#         self.next_run = None
#         self.event_loop = event_loop

#     def set_event_loop(self, event_loop:asyncio.AbstractEventLoop):
#         self.event_loop = event_loop

#     def start(self):
#         if self.event_loop is None or self.event_loop.is_closed():
#             return False
#         'method to get the repeating cleaning task to start'
#         if self.status in [CLEANING_STATE.RUNNING, CLEANING_STATE.STARTING]:
#             return False
#         self.task = self.event_loop.create_task(self.clean_task)
#         self.status = CLEANING_STATE.STARTING
#         self.next_run = datetime.utcnow()
#         return True

#     def stop(self):
#         if self.status in [CLEANING_STATE.STOPPING, CLEANING_STATE.STOPPED]:
#             return False
#         # res = self.cleaning_task.cancel()
#         # cleaning_logger.debug(f"result from canceling attempt, {res}")
#         self.status = CLEANING_STATE.STOPPING
#         return True

#     def clean_task(self):
#         this_cleaning = asyncio.current_task()
#         while self.status in [CLEANING_STATE.STARTING, CLEANING_STATE.RUNNING]:
#             self.status = CLEANING_STATE.RUNNING
#             starttime = datetime.utcnow()


class CacheEntry:
    def __init__(self, primary_key, data, timeout=180) -> None:
        self.primary_key = primary_key
        self.data = data
        self.set_TTL(timeout_duration=timedelta(seconds=timeout))

    def set_TTL(self, timeout_duration:timedelta):
        if timeout_duration.total_seconds() == -1:
            # specifically, don't time out
            self.timeout = None
        else:
            self.timeout = datetime.utcnow() + timeout_duration

class Index:
    # purpose is to provide a lookup to objects in cache
    def __init__(self, name) -> None:
        self.name = name
        self.pointers:dict[typing.Hashable, set[typing.Hashable]] = {}
        self.cache = None

    def set_cache(self, cache:"Cache"):
        '''sets the cache this index is connected to and all data is in reference to'''
        self.cache = cache
        self.pointers = {}
        if not cache.is_empty():
            for key, entry in cache:
                self.add_entry(key, entry.data)

    def iter(self, key):
        '''creates and returns an interator through all primary keys of entries that fall under given key in this index'''
        return iter(self.pointers.get(key, set()))

    def add_pointer(self, primary_key, secondary_key):
        if isinstance(secondary_key, typing.Hashable):
            if secondary_key not in self.pointers:
                self.pointers[secondary_key] = set()
            self.pointers[secondary_key].add(primary_key)

    def del_pointer(self, primary_key, secondary_key):
        if isinstance(secondary_key, typing.Hashable) and secondary_key in self.pointers:
            self.pointers[secondary_key].remove(primary_key)
            if len(self.pointers[secondary_key]) == 0:
                del self.pointers[secondary_key]

    def get(self, key, default=None):
        '''
        returns the set of primary keys that fall under the given key in this index'''
        return self.pointers.get(key, default)

    def add_entry(self, primary_key, to_add_values):
        '''index callback when entry is added to cache, or setting up index. Must implement in child classes. Cache itself will only call this
         when inserting a new key value pair. Meant for indices to sort out if entry should be indexed and with what value'''
        pass

    def update_entry(self, primary_key, to_update_values, already_updated=False, field_update_strat=UPDATE_STRAT.ADD):
        '''index callback when an entry that exists in the cache is updated. Must implement in child classes. Meant for checking
        if the values that define this index were changed or not and assigning a different place'''
        pass

    def set_entry(self, primary_key, to_update_values):
        '''index callback when an entry that exists in the cache has all its data set to new stuff. Must implement in child classes.
        Meant for checking if the values that define this index were changed or not and assigning a different place'''
        pass

    def del_entry(self, primary_key, cache_entry:CacheEntry):
        '''index callback when an entry is deleted from cache. Must implement in child classes. Mean for removing items from reference and
        cleaning up any now-hanging index structure'''
        pass

    def emergency_cleanup(self, delete_pks = None):
        '''clean up any dead references to any key in the passed in list'''
        if delete_pks is None:
            self.pointers.clear()
            return
        for pk in delete_pks:
            for k, pk_list in list(self.pointers.items()):
                if pk in pk_list:
                    self.pointers[k].remove(pk)
                if len(pk_list) == 0:
                    del self.pointers[k]

    def __len__(self):
        return len(self.pointers)

class SimpleIndex(Index):
    def __init__(self, name, col_name) -> None:
        super().__init__(name)
        self.col_name = col_name

    def add_entry(self, primary_key, to_add_values):
        '''index callback when entry is added or changed'''
        if self.col_name in to_add_values:
            key_val = to_add_values[self.col_name]
            if key_val not in self.pointers:
                self.pointers[key_val] = set()
            self.pointers[key_val].add(primary_key)

    def update_entry(self, primary_key, to_update_values, already_updated=False, field_update_strat=UPDATE_STRAT.ADD):
        if self.col_name in to_update_values:
            # only need to update if keyed area could be updated
            # method is only meant to be called if key already exists so grabbing entry from cache shouldn't break
            cache_entry = self.cache.get_key(primary_key, index_name="primary")[0]
            cache_entry = self.cache.data[cache_entry]
            cachev2_logger.debug(f"testing update entry, grabbing cache entry {cache_entry}")
            self.del_entry(primary_key, cache_entry)
            if field_update_strat == UPDATE_STRAT.SET or field_update_strat == UPDATE_STRAT.ADD:
                self.add_entry(primary_key, to_update_values)

    def set_entry(self, primary_key, to_update_values):
        cache_entry = self.cache.data[self.cache.get_key(primary_key, index_name="primary")[0]]
        self.del_entry(primary_key, cache_entry)
        self.add_entry(primary_key, to_update_values)

    def del_entry(self, primary_key, cache_entry: CacheEntry):
        if self.col_name in cache_entry.data:
            key_val = cache_entry.data[self.col_name]
            if key_val in self.pointers:
                self.pointers[key_val].remove(primary_key)
                if len(self.pointers[key_val]) == 0:
                    del self.pointers[key_val]

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

    def add_entry(self, primary_key, to_add_values):
        if self.col_name in to_add_values:
            if isinstance(to_add_values[self.col_name], typing.Hashable):
                super().add_entry(primary_key=primary_key, to_add_values=to_add_values)
            else:
                for key_val in to_add_values[self.col_name]:
                    self.add_pointer(primary_key, key_val)

    def update_entry(self, primary_key, to_update_values, already_updated=False, field_update_strat=UPDATE_STRAT.ADD):
        if self.col_name in to_update_values:
            # only need to update if keyed area could be updated
            # method is only meant to be called if key already exists so grabbing entry from cache shouldn't break
            cache_entry = self.cache.get_key(primary_key, index_name="primary")[0]
            cache_entry = self.cache.data[cache_entry]
            cachev2_logger.debug(f"testing update entry, grabbing cache entry {cache_entry}")
            if field_update_strat == UPDATE_STRAT.SET:
                self.del_entry(primary_key, cache_entry)
                self.add_entry(primary_key, to_update_values)
            elif field_update_strat == UPDATE_STRAT.ADD:
                self.add_entry(primary_key, to_update_values)
            else:
                # DELETE mode
                if type(cache_entry.data[self.col_name]) is dict or type(cache_entry.data[self.col_name]) is list or type(cache_entry.data[self.col_name]) is set:
                    if to_update_values[self.col_name] is not None:
                        for key_val in to_update_values[self.col_name]:
                            self.del_pointer(primary_key, key_val)
                    else:
                        for key_val in cache_entry.data[self.col_name]:
                            self.del_pointer(primary_key, key_val)
                else:
                    self.del_pointer(primary_key, cache_entry.data[self.col_name])

    def del_entry(self, primary_key, cache_entry: CacheEntry):
        if self.col_name in cache_entry.data:
            if type(cache_entry.data[self.col_name]) is dict or type(cache_entry.data[self.col_name]) is list or type(cache_entry.data[self.col_name]) is set:
                for key_val in cache_entry.data[self.col_name]:
                    self.del_pointer(primary_key, key_val)
            else:
                super().del_entry(primary_key=primary_key, cache_entry=cache_entry)

class Cache:
    '''
    assumes primary key only has one object associated with it
    '''
    # get and delete (maybe others too) based on multiple keys??
    def __init__(self, secondaryIndices = [], defualt_get_copy_rule = COPY_RULES.ORIGINAL, default_timeout=180) -> None:
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

        self.secondary_indices:dict[str, Index] = {}
        '''dict of index objects providing other ways to find objects'''
        self.default_get_copy_rule = defualt_get_copy_rule
        self.data:dict[typing.Any, CacheEntry] = {}
        '''the actual dictionary storing data, primary key to data'''
        self.default_timeout = default_timeout

        self.cleaning_task = None
        self.cleaning_status = {"state":CLEANING_STATE.STOPPED, "next": None, "now": None}
        self.add_indices(secondaryIndices)

    def add_indices(self, secondaryIndices=[]):
        for index in secondaryIndices:
            if type(index) is str:
                if index == "primary":
                    cachev2_logger.warning("trying to add index named 'primary' but that's a reserved name. skipping")
                    continue
                if index in self.secondary_indices:
                    cachev2_logger.warning(f"trying to add index named {index} but that exists already. skipping")
                    continue
                # assuming what's there is the name
                self.secondary_indices[index] = SimpleIndex(index, index)
                self.secondary_indices[index].set_cache(self)
            elif issubclass(type(index), Index):
                if index.name == "primary":
                    cachev2_logger.warning("trying to add index named 'primary' but that's a reserved name. skipping")
                    continue
                if index.name in self.secondary_indices:
                    cachev2_logger.warning(f"trying to add index named {index.name} but that exists already. skipping")
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
        If entries are found, returns a list of one or more primary keys. Copied using copy rules
        If no entries are found, returns the value of default'''
        override_copy_rule=COPY_RULES.DEEP
        if index_name == "primary" or index_name == "":
            cachev2_logger.debug(f"getting data from primary index")
            if key in self.data:
                # don't want to format default value into a list so there's a filter
                # primary index assumed to have only one entry mapped, so format it as a list
                return [self.apply_copy_rule(key, override_copy_rule=override_copy_rule)]
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
            return [self.apply_copy_rule(primary_key, override_copy_rule=override_copy_rule) for primary_key in primary_keys]

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
            return [self.apply_copy_rule(self.data.get(primary_key).data, override_copy_rule=override_copy_rule) for primary_key in result]

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
        if key is None:
            #note: not sure if this generates IDs in a way that is same for multithreading or multiprocessing. It should? Documentation doesn't say it isn't either
            key = uuid.uuid4().hex
        if value is None:
            value = {}

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

        cachev2_logger.debug(f"adding data to cache, key: <{key}>, value <{value}>")
        if key in self.data:
            if not or_overwrite:
                # if key is recorded and not allowed to overwrite, then can't do anything
                return None
            # allowed to overwrite previous data, so technically a set rather than an add
            return self.set(key=key, value=value, index_name='primary', addition_copy_rule=addition_copy_rule)
        else:
            # index_additions = {}
            for index in self.secondary_indices.values():
                index.add_entry(key, to_add)
                # index_calc = index.add_entry(key, to_add)
                # if index_calc is not None:
                #     index_additions.update(index_calc)
            # to_add.update(index_additions)
            self.data[key] = CacheEntry(key, to_add, timeout=self.default_timeout)

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
                if id(value) == id(self.data.get(key).data):
                    # passed in values is same object as what is already stored for the key. techincally possible to dig and grab but also want to provide way to get it anyways
                    # case with a couple implications:
                    #   data could be directly touched and indices will not get automatically updated based off of changes thare aren't done through cache methods
                    #   these changes already are in cache when cache update/set/delete functions are being called, while update index assumes it isn't
                    if field_update_strat == UPDATE_STRAT.DELETE:
                        self.data.get(key).data.clear()
                    for index in self.secondary_indices.values():
                        index.emergency_cleanup([key])
                        cachev2_logger.debug(f"emergency cleaning out key {key} from index {index.name}")
                        index.update_entry(key, value, already_updated=True, field_update_strat=field_update_strat)
                    
                    return self.data.get(key)
                
                # only do rest of function if update values passed in is not same object as actual storage
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

                # now adding, tell about updates before updates in case index depends on current state
                for index in self.secondary_indices.values():
                    index.update_entry(key, to_update, field_update_strat=field_update_strat)

                # actual update of data
                if field_update_strat == UPDATE_STRAT.SET:
                    self.data.get(key).data.update(to_update)
                elif field_update_strat == UPDATE_STRAT.DELETE:
                    # passed in values are fields to be deleted, or for lists, sets and dicts what sub items/keys to be deleted
                    cache_entry = self.data.get(key)
                    for update_key, update_data in to_update.items():
                        if update_key in cache_entry.data:
                            field_value = cache_entry.data.get(update_key)
                            if type(field_value) is list:
                                if update_data is None:
                                    del cache_entry.data[update_key]
                                    continue
                                for secondary_key in update_data:
                                    field_value.remove(secondary_key)
                                continue
                            elif type(field_value) is dict:
                                if update_data is None:
                                    del cache_entry.data[update_key]
                                    continue
                                for secondary_key in update_data:
                                    del field_value[secondary_key]
                                continue
                            elif type(field_value) is set:
                                if update_data is None:
                                    del cache_entry.data[update_key]
                                    continue
                                for secondary_key in update_data:
                                    field_value.remove(secondary_key)
                                continue
                            del cache_entry.data[update_key]
                else:
                    # add strat, means any new fields get added, if there's an existing collection, add items to it (only if possible), otherwise does set too
                    for update_key, update_data in to_update.items():
                        # to_update is dict of all things to update
                        if update_key in self.data.get(key).data:
                            if type(self.data.get(key).data[update_key]) is list:
                                if type(update_data) is list or type(update_data) is set:
                                    self.data.get(key).data[update_key].extend(update_data)
                                continue
                            elif type(self.data.get(key).data[update_key]) is dict:
                                if type(update_data) is dict:
                                    self.data.get(key).data[update_key].update(update_data)
                                continue
                            elif type(self.data.get(key).data[update_key]) is set:
                                if type(update_data) is set or type(update_data) is list:
                                    for update_data_entry in update_data:
                                        self.data.get(key).data[update_key].add(update_data_entry)
                                continue
                        # either key isn't in data so can just set value, or key inside and isn't a nested collection so behaves like a set value
                        self.data.get(key).data[update_key] = update_data
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
                
                if id(value) == id(self.data.get(key).data):
                    # if update called and passed in original data, assuming likely modified data without going through cache commands
                    # which will mean indices dont get updated so do reindex stuff
                    for index in self.secondary_indices.values():
                        index.emergency_cleanup([key])
                for index in self.secondary_indices.values():
                    index.set_entry(key, value)
                self.data.get(key).data=to_update
                self.data.get(key).set_TTL(timedelta(seconds=self.default_timeout))
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
                    index.del_entry(key, value)
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

    def reindex(self, updated_keys:'typing.Union[str, list[str], None]'=None):
        if updated_keys is None:
            updated_keys = list(self.data.keys())
        if type(updated_keys) is not list:
            updated_keys = [updated_keys]

        for key in updated_keys:
            if key not in self.data:
                continue
            for index in self.secondary_indices.values():
                index.emergency_cleanup([key])
                index.update_entry(key, self.get(key=key, index_name="primary")[0])

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