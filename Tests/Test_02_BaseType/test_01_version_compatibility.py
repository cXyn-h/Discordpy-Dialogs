import src.DialogNodes.BaseType as BaseType
import yaml
import pytest

def test_compatible():
    '''loaded type should be compatible with itself. sanity checking that'''
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility(BaseType.BaseGraphNode.get_version())
    assert is_compatible == True

def test_invalid_version_string():
    '''tests for validating version strings behaves as expected'''
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("asdf.4.5")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("4.$.5")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("4.6.5f")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("4.6.5.3")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("4.6")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("6")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("-4.6.5")
    assert is_compatible == False
    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility("4.-6.5")
    assert is_compatible == False

def test_version_mismatches():
    version_string = BaseType.BaseGraphNode.get_version()
    first_dot=version_string.find(".")
    second_dot=version_string.find(".",first_dot+1)
    version_tuple=(int(version_string[:first_dot]),int(version_string[first_dot+1:second_dot]), int(version_string[second_dot+1:]))

    # for base type, major mismatch is first number different
    major_mismatch = [str(val - 1)  if ind == 0 else str(val) for ind, val in enumerate(version_tuple)]
    # for base type, minor mismatch is second number different
    minor_mismatch = [str(val - 1)  if ind == 1 else str(val) for ind, val in enumerate(version_tuple)]

    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility(".".join(major_mismatch))
    assert is_compatible == False

    is_compatible, errors = BaseType.BaseGraphNode.check_version_compatibility(".".join(minor_mismatch))
    assert is_compatible == True

#TODO more base type test cases