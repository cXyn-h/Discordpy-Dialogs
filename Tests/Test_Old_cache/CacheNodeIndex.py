from Tests.Test_Old_cache.Cache_old import AbstractIndex, AbstractCacheEntry
import src.DialogNodes.BaseType as BaseType
import typing

class CacheNodeIndex(AbstractIndex):
    '''index for cache storing active node objects'''
    def __init__(self, name, indexing_field:typing.Literal["event", "session", "status"]) -> None:
        super().__init__(name)
        if indexing_field not in ["event", "session", "status", "graph_node"]:
            raise Exception(f"Index for active Nodes stored in Dialog handler given a field name that it does not support indexing on. must be 'event', 'session', 'status', or 'graph_node")
        self.indexing_field = indexing_field

    def parse_for_keys(self, entry: AbstractCacheEntry):
        if not issubclass(entry.__class__, BaseType.BaseNode):
            return []
        if self.indexing_field == "session":
            return [id(entry.session)]
        elif self.indexing_field == "event":
            return list(entry.graph_node.get_events().keys())
        elif self.indexing_field == "status":
            return [entry.status]
        elif self.indexing_field == "graph_node":
            return entry.graph_node.id
        else:
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
