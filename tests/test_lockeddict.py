import pytest

from lockeddict import LockedDict


def test_dummy():
    # Arrange
    # Act
    pass
    # Assert


def test___init__():
    # Act
    mylockeddict = LockedDict()
    # Assert
    assert dict(mylockeddict.items()) == {}

    # Act
    mylockeddict = LockedDict({})
    # Assert
    assert dict(mylockeddict.items()) == {}

    # Act
    mylockeddict = LockedDict({'alfa': 1, 'bravo': 2, 'charlie': 3})
    # Assert
    assert dict(mylockeddict.items()) == {'alfa': 1, 'bravo': 2, 'charlie': 3}


def test_pop():
    # Arrange
    mylockeddict = LockedDict({'alfa': 1, 'bravo': 2, 'charlie': 3})

    # Act
    value = mylockeddict.pop('alfa')

    # Assert
    assert value == 1
    assert dict(mylockeddict.items()) == {'bravo': 2, 'charlie': 3}


def test_pop_with_default():
    # Arrange
    mylockeddict = LockedDict()

    # Act & Assert
    value = mylockeddict.pop('bad key', None)
    assert value is None
    assert dict(mylockeddict.items()) == {}

    # Act & Assert
    value = mylockeddict.pop('bad key', False)
    assert value == False
    assert dict(mylockeddict.items()) == {}


def test_pop_with_exception():
    # Arrange
    mylockeddict = LockedDict()

    # Act & Assert
    with pytest.raises(TypeError):
        # TypeError: dict.pop() takes no keyword arguments
        value = mylockeddict.pop('key', default=None)

    # Act & Assert
    with pytest.raises(TypeError):
        # TypeError: pop expected at most 2 arguments, got 3
        value = mylockeddict.pop('key', 'arg2', 'arg3')

    # Act & Assert
    with pytest.raises(KeyError):
        value = mylockeddict.pop('bad key')
