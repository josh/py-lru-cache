import atexit
import logging
import pickle
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from pathlib import Path
from typing import Any

__author__ = "Joshua Peek"
__url__ = "https://raw.githubusercontent.com/josh/py-lru-cache/main/lru_cache.py"
__license__ = "MIT"
__copyright__ = "Copyright 2024 Joshua Peek"

_logger = logging.getLogger("lru_cache")
_caches_to_save: list["LRUCache"] = []

_SENTINEL = object()


class LRUCache:
    """Persisted least recently used key-value cache."""

    path: Path | None
    _data: OrderedDict[Hashable, Any]
    _max_bytesize: int
    _did_change: bool = False

    def __init__(
        self,
        path: Path | None = None,
        max_bytesize: int = 1024 * 1024,  # 1 MB
        save_on_exit: bool = False,
    ) -> None:
        """Create a new LRUCache."""
        self.path = path
        self._data = OrderedDict()
        self._max_bytesize = max_bytesize
        self._load()
        if save_on_exit:
            _caches_to_save.append(self)

    def _load(self) -> None:
        if self.path is None:
            return

        if not self.path.exists():
            _logger.debug("persisted cache not found: %s", self.path)
            return

        with self.path.open("rb") as f:
            self._data.update(pickle.load(f))
        self._did_change = False

    def save(self) -> None:
        """Save the cache to disk."""
        if not self.path:
            _logger.error("failed to save LRU cache: no path provided")
            return

        if self._did_change is False:
            _logger.info("no changes to save")
            return

        self.trim()
        _logger.debug("saving cache: %s", self.path)
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as f:
            pickle.dump(self._data, f, pickle.HIGHEST_PROTOCOL)

    def trim(self) -> int:
        """Trim the cache to fit within the max bytesize."""
        sorted_keys = list(self._data.keys())
        count = 0
        while self.bytesize() > self._max_bytesize:
            key = sorted_keys.pop(0)
            self._did_change = True
            del self._data[key]
            count += 1
        if count > 0:
            _logger.debug("trimmed %i items", count)
        return count

    def __getitem__(self, key: Hashable) -> Any | None:
        """Return value for key in cache, else None."""
        value = self._data.get(key, _SENTINEL)
        if value is _SENTINEL:
            _logger.debug("miss key=%s", key)
            return None
        else:
            _logger.debug("hit key=%s", key)
            self._did_change = True
            self._data.move_to_end(key, last=True)
            return value

    def __setitem__(self, key: Hashable, value: Any) -> None:
        """Set value for key in cache."""
        _logger.debug("set key=%s", key)
        self._did_change = True
        self._data[key] = value
        self._data.move_to_end(key, last=True)

    def __delitem__(self, key: Hashable) -> None:
        """Delete key from cache."""
        _logger.debug("del key=%s", key)
        self._did_change = True
        del self._data[key]

    def __contains__(self, key: Hashable) -> bool:
        """Return True if key is in the cache."""
        return key in self._data

    def __iter__(self) -> Iterator[Hashable]:
        """Iterate over keys in the cache."""
        return iter(self._data)

    def items(self) -> Iterator[tuple[Hashable, Any]]:
        """Iterate over key-value pairs in the cache."""
        yield from self._data.items()

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        return len(self._data)

    def bytesize(self) -> int:
        """Return the persisted size of the cache in bytes."""
        return len(pickle.dumps(self._data))

    def get(self, key: Hashable, load_value: Callable[[], Any]) -> Any:
        """Get value for key in cache, else load the value and store it in the cache."""
        value = self._data.get(key, _SENTINEL)
        if value is _SENTINEL:
            _logger.debug("miss key=%s", key)
            value = load_value()
            self._did_change = True
            self._data[key] = value
            return value
        else:
            _logger.debug("hit key=%s", key)
            self._did_change = True
            self._data.move_to_end(key, last=True)
            return value


def _save_caches() -> None:
    for cache in _caches_to_save:
        cache.save()


atexit.register(_save_caches)
