from __future__ import annotations

import hashlib


class Cache:
    def __init__(self) -> None:
        self._results: dict[str, bool] = {}

    def get(self, source: bytes) -> bool | None:
        return self._results.get(_key(source))

    def set(self, source: bytes, result: bool) -> None:
        self._results[_key(source)] = result


def _key(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()[:16]
