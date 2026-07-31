"""Provide class for a dict with thread-safety.

When you need to perform multiple steps with a LockedDict object, such 
as checking if a key exists before changing it, wrap the entire logic in 
the lock. This ensures no other thread can intervene during the sequence.

https://www.google.com/search?q=python+subclass+dict+to+provide+a+thread-safe+object

A More Pythonic Alternative: Composition (Wrapping)
Instead of subclassing, many Python developers prefer using composition
(wrapping the dictionary) and exposing only the necessary thread-safe
methods. This limits the surface area you need to protect and is often
considered a better design choice than trying to override every single
dict method.

Why use threading.RLock instead of threading.Lock?
    A Lock can only be acquired once by a thread, while an RLock
    (reentrant lock) can be acquired multiple times by the same thread
    without causing a deadlock.

https://medium.com/@abhishekjainindore24/advanced-python-10-lock-vs-rlock-c747bbdbd803
When do you actually need RLock?
    Use RLock when:
    *   A function acquires a lock
    *   That function calls another function
    *   The inner function also needs the same lock
    Common cases:
    *   Recursive functions
    *   Class methods calling other methods
"""

import threading


class LockedDict:
    """A dict-like object, with a public lock and thread-safe methods."""

    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)
        self.lock = threading.RLock()  # Publicly accessible lock

    def __contains__(self, *args, **kwargs):
        with self.lock:
            return self._dict.__contains__(*args, **kwargs)

    def __delitem__(self, *args, **kwargs):
        with self.lock:
            return self._dict.__delitem__(*args, **kwargs)

    # Define other necessary methods as needed (e.g., keys, values,
    # items, __len__ etc.)

    # A statement like "lockeddict[key] = value" uses the __setitem__ method
    def __setitem__(self, *args, **kwargs):
        with self.lock:
            return self._dict.__setitem__(*args, **kwargs)

    # A statement like "value = lockeddict[key]" uses the __getitem__ method
    def __getitem__(self, *args, **kwargs):
        with self.lock:
            return self._dict.__getitem__(*args, **kwargs)

    # A statement like "len(lockeddict)" uses the __len__ method
    def __len__(self, *args, **kwargs):
        with self.lock:
            return self._dict.__len__(*args, **kwargs)

    def get(self, *args, **kwargs):
        with self.lock:
            return self._dict.get(*args, **kwargs)

    def items(self, *args, **kwargs):
        with self.lock:
            return self._dict.items(*args, **kwargs)

    def keys(self, *args, **kwargs):
        with self.lock:
            return self._dict.keys(*args, **kwargs)

    def pop(self, *args, **kwargs):
        with self.lock:
            return self._dict.pop(*args, **kwargs)
