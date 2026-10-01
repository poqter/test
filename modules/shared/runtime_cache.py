"""Bounded per-session last-result cache; never a shared cache of customer data.

Failures are never cached. Keys are fingerprints; telemetry contains only
counters/timings. A byte budget evicts older entries rather than retaining all
historical uploads and downloads. With no Streamlit context the producer runs
normally, keeping pure CLI generation and unit tests independent of Streamlit.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from io import BytesIO
import sys
import time
from collections import OrderedDict
from collections.abc import MutableMapping
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Callable

CACHE_KEY = "hw.runtime_cache.v1"
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 16


def digest_bytes(data: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(data).hexdigest()


def _serial(value: Any) -> Any:
    if isinstance(value, BytesIO):
        return {"stream_sha256": digest_bytes(value.getvalue()), "length": value.getbuffer().nbytes}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"bytes_sha256": digest_bytes(value), "length": len(value)}
    if isinstance(value, (Decimal, date, datetime)):
        return {"type": type(value).__name__, "value": str(value)}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serial(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serial(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_serial(v) for v in value), key=str)
    if hasattr(value, "to_dict") and hasattr(value, "columns"):
        return {"columns": list(map(str, value.columns)), "dtypes": list(map(str, value.dtypes)), "index": _serial(value.index.tolist()), "records": _serial(value.to_dict(orient="records"))}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Only a digest is retained; this fallback never appears in logs or the UI.
    return {"type": type(value).__name__, "repr": repr(value)}


def fingerprint(*values: Any) -> str:
    payload = json.dumps(_serial(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return digest_bytes(payload.encode("utf-8"))


def _session():
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:
            return None
        return st.session_state
    except (ImportError, AttributeError):
        return None


def estimate_bytes(value: Any, seen: set[int] | None = None) -> int:
    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    if hasattr(value, "memory_usage") and hasattr(value, "columns"):
        return int(value.memory_usage(index=True, deep=True).sum())
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        return size + sum(estimate_bytes(k, seen) + estimate_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return size + sum(estimate_bytes(v, seen) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return size + sum(estimate_bytes(getattr(value, f.name), seen) for f in dataclasses.fields(value))
    return size


def cached(scope: str, signature: str, producer: Callable[[], Any], *, state=None,
           max_bytes: int = MAX_CACHE_BYTES) -> Any:
    session = _session() if state is None else state
    if session is None:
        return producer()
    store = session.get(CACHE_KEY)
    if not isinstance(store, dict):
        store = {"entries": OrderedDict(), "hits": 0, "builds": 0, "seconds": 0.0}
        session[CACHE_KEY] = store
    entries = store["entries"]
    entry = entries.get(scope)
    if entry and entry["signature"] == signature:
        entries.move_to_end(scope)
        store["hits"] += 1
        return entry["value"]
    # Remove the superseded object before producing a replacement.
    entries.pop(scope, None)
    start = time.perf_counter()
    value = producer()  # Raising leaves no cached failure or stale replacement.
    store["seconds"] += time.perf_counter() - start
    store["builds"] += 1
    size = estimate_bytes(value)
    if size <= max_bytes:
        while entries and (len(entries) >= MAX_ENTRIES or sum(e["size"] for e in entries.values()) + size > max_bytes):
            entries.popitem(last=False)
        entries[scope] = {"signature": signature, "value": value, "size": size}
    return value


def clear_scope(prefix: str, *, state=None) -> None:
    session = _session() if state is None else state
    if session is None:
        return
    store = session.get(CACHE_KEY, {})
    for key in list(store.get("entries", {})):
        if key.startswith(prefix):
            del store["entries"][key]


def statistics(*, state=None) -> dict[str, int | float]:
    session = _session() if state is None else state
    store = session.get(CACHE_KEY, {}) if session is not None else {}
    return {"entries": len(store.get("entries", {})),
            "bytes": sum(e["size"] for e in store.get("entries", {}).values()),
            "hits": store.get("hits", 0), "builds": store.get("builds", 0),
            "seconds": round(store.get("seconds", 0.0), 4)}


def session_export(version: str, *, name_arg: bool = True):
    """Cache at most the latest output per export function and calculator name."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            name = str(args[0]) if name_arg and args and isinstance(args[0], str) else "last"
            # Deployment configuration affects branding, and belongs in the key.
            from modules.shared.organization import current_brand_fingerprint
            scope = "export:" + function.__module__ + "." + function.__name__ + ":" + name
            key = fingerprint(version, args, kwargs, date.today().isoformat(), current_brand_fingerprint())
            value = cached(scope, key, lambda: function(*args, **kwargs))
            # Never expose the cached cursor of a mutable in-memory file.
            if isinstance(value, BytesIO):
                return BytesIO(value.getvalue())
            return value
        return wrapped
    return decorate
