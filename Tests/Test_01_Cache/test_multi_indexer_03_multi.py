import pytest
import src.utils.Cache as CC

def test_multiindex_create():
    test_mi = CC.MultiIndexer()
    assert test_mi.cache == {}
    assert test_mi.secondary_indices == {}
    assert not test_mi.is_cache_obj
    assert not test_mi.is_cache_set

    test_cache = CC.Cache()
    test_mi2 = CC.MultiIndexer(cache=test_cache)
    assert test_mi2.cache is test_cache
    assert test_mi2.is_cache_obj
    assert test_mi2.is_cache_set
    assert test_mi2.secondary_indices == {}

    test_cache = {}
    test_mi2 = CC.MultiIndexer(cache=test_cache)
    assert test_mi2.cache is test_cache
    assert not test_mi2.is_cache_obj
    assert test_mi2.is_cache_set
    assert test_mi2.secondary_indices == {}

def test_multiindex_set_cache():
    test_mi = CC.MultiIndexer()
    test_cache = CC.Cache()
    test_mi.set_cache(test_cache)
    assert test_mi.cache is test_cache
    assert test_mi.is_cache_obj
    assert test_mi.is_cache_set
    assert test_mi.secondary_indices == {}

def test_multiindex_init_with_index():
    test_mi = CC.MultiIndexer(input_secondary_indices=["test", CC.FieldValueIndex("test2", "test2")])
    assert test_mi.cache == {}
    assert len(test_mi.secondary_indices) == 2
    assert "test" in test_mi.secondary_indices
    assert isinstance(test_mi.secondary_indices["test"], CC.FieldValueIndex)
    assert "test2" in test_mi.secondary_indices
    assert isinstance(test_mi.secondary_indices["test2"], CC.FieldValueIndex)

def test_multiindex_add_index():
    test_mi = CC.MultiIndexer()
    test_i = CC.FieldValueIndex("test", "test2")
    test_mi.add_indices(test_i)
    assert len(test_mi.secondary_indices) == 1
    assert test_mi.secondary_indices["test"] is test_i

def test_multiindex_add_index_fails():
    test_i1 = CC.FieldValueIndex("test", "test2")
    test_i2 = CC.FieldValueIndex("test", "test2")
    test_mi = CC.MultiIndexer(input_secondary_indices=[test_i1])
    test_mi.add_indices(test_i2)
    assert len(test_mi.secondary_indices) == 1
    assert test_mi.secondary_indices["test"] is test_i1

    test_i3 = CC.FieldValueIndex("primary", "test2")
    test_mi.add_indices(test_i3)
    assert len(test_mi.secondary_indices) == 1

def test_multiindex_remove_index():
    test_mi = CC.MultiIndexer(input_secondary_indices=["test", CC.FieldValueIndex("test2", "test2")])
    test_mi.remove_indices("test", "test2")
    assert len(test_mi.secondary_indices) == 0
