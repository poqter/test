"""Small Streamlit compatibility stub for non-browser release smoke tests.

The production app still runs against the pinned Streamlit package. This stub
only exercises import paths and first-render code in environments where the
package is unavailable.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import sys
import types
from typing import Any, Iterable


class SessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class DummyElement:
    def __init__(self, api: "StreamlitAPI" | None = None) -> None:
        self.api = api

    def __enter__(self) -> "DummyElement":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def __call__(self, *args: Any, **kwargs: Any) -> "DummyElement":
        return self

    def __getattr__(self, _name: str):
        def method(*_args: Any, **_kwargs: Any) -> "DummyElement":
            if self.api is not None:
                self.api.events.append({"kind": _name, "args": _args, "kwargs": _kwargs})
            return self
        return method

    def container(self, *args: Any, **kwargs: Any) -> "DummyElement":
        return DummyElement(self.api)

    def columns(self, spec: int | Iterable[Any], **kwargs: Any) -> list["DummyElement"]:
        count = spec if isinstance(spec, int) else len(tuple(spec))
        return [DummyElement(self.api) for _ in range(int(count))]

    def tabs(self, labels: Iterable[str], **kwargs: Any) -> list["DummyElement"]:
        return [DummyElement(self.api) for _ in labels]

    def empty(self) -> "DummyElement":
        return DummyElement(self.api)

    # Widgets called on columns/containers delegate to the module API so their
    # return values match first-render Streamlit behavior.
    def button(self, *args: Any, **kwargs: Any) -> bool:
        if isinstance(self, DummyElement) and self.api is not None:
            return self.api.button(*args, **kwargs)
        self.events.append({"kind": "button", "args": args, "kwargs": kwargs})
        key = kwargs.get("key", args[0] if args else "")
        clicked = key in self.clicked and not kwargs.get("disabled", False)
        if clicked:
            self.clicked.discard(key)
            callback = kwargs.get("on_click")
            if callable(callback):
                callback(*kwargs.get("args", ()), **kwargs.get("kwargs", {}))
        return clicked

    def link_button(self, *args: Any, **kwargs: Any) -> "DummyElement":
        if self.api is not None:
            self.api.events.append({"kind": "link_button", "args": args, "kwargs": kwargs})
        return DummyElement(self.api)

    def download_button(self, *args: Any, **kwargs: Any) -> bool:
        api = self.api if isinstance(self, DummyElement) else self
        if api is not None:
            api.events.append({"kind": "download_button", "args": args, "kwargs": kwargs})
        return False

    def form_submit_button(self, *args: Any, **kwargs: Any) -> bool:
        return self.button(*args, **kwargs)

    def text_input(self, *args: Any, **kwargs: Any) -> str:
        return self.api.text_input(*args, **kwargs) if self.api else str(kwargs.get("value", ""))

    def text_area(self, *args: Any, **kwargs: Any) -> str:
        return self.api.text_area(*args, **kwargs) if self.api else str(kwargs.get("value", ""))

    def number_input(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.number_input(*args, **kwargs) if self.api else kwargs.get("value", 0)

    def date_input(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.date_input(*args, **kwargs) if self.api else kwargs.get("value", date.today())

    def selectbox(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.selectbox(*args, **kwargs) if self.api else None

    def radio(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.radio(*args, **kwargs) if self.api else None

    def multiselect(self, *args: Any, **kwargs: Any) -> list[Any]:
        return self.api.multiselect(*args, **kwargs) if self.api else list(kwargs.get("default", []))

    def checkbox(self, *args: Any, **kwargs: Any) -> bool:
        return self.api.checkbox(*args, **kwargs) if self.api else bool(kwargs.get("value", False))

    def toggle(self, *args: Any, **kwargs: Any) -> bool:
        return self.checkbox(*args, **kwargs)

    def slider(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.slider(*args, **kwargs) if self.api else kwargs.get("value")

    def select_slider(self, *args: Any, **kwargs: Any) -> Any:
        return self.api.select_slider(*args, **kwargs) if self.api else kwargs.get("value")

    def data_editor(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        api = self.api if isinstance(self, DummyElement) else self
        if api is not None:
            api.events.append({"kind": "data_editor", "args": args, "kwargs": kwargs})
            data = api.edited_tables.get(kwargs.get("key"), data)
        return data.copy() if hasattr(data, "copy") else data


class ColumnConfig:
    def __getattr__(self, _name: str):
        def config(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"args": args, **kwargs}
        return config


class CacheDecorator:
    def __call__(self, func=None, **_kwargs: Any):
        if func is None:
            return lambda inner: inner
        return func

    def clear(self) -> None:
        return None


class StreamlitAPI:
    def __init__(self) -> None:
        self.session_state = SessionState()
        self.events: list[dict[str, Any]] = []
        self.strict_numeric = False
        self.clicked: set[str] = set()
        self.edited_tables: dict[str, Any] = {}
        self.secrets: dict[str, Any] = {}
        self.query_params: dict[str, Any] = {}
        self.sidebar = DummyElement(self)
        self.column_config = ColumnConfig()
        self.cache_data = CacheDecorator()
        self.cache_resource = CacheDecorator()

    def _state_value(self, key: str | None, default: Any) -> Any:
        if key is None:
            return default
        if key not in self.session_state:
            self.session_state[key] = default
        return self.session_state[key]

    def container(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def columns(self, spec: int | Iterable[Any], **kwargs: Any) -> list[DummyElement]:
        count = spec if isinstance(spec, int) else len(tuple(spec))
        return [DummyElement(self) for _ in range(int(count))]

    def tabs(self, labels: Iterable[str], **kwargs: Any) -> list[DummyElement]:
        return [DummyElement(self) for _ in labels]

    def empty(self) -> DummyElement:
        return DummyElement(self)

    def form(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def expander(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def popover(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def spinner(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def status(self, *args: Any, **kwargs: Any) -> DummyElement:
        return DummyElement(self)

    def button(self, *args: Any, **kwargs: Any) -> bool:
        if isinstance(self, DummyElement) and self.api is not None:
            return self.api.button(*args, **kwargs)
        self.events.append({"kind": "button", "args": args, "kwargs": kwargs})
        key = kwargs.get("key", args[0] if args else "")
        clicked = key in self.clicked and not kwargs.get("disabled", False)
        if clicked:
            self.clicked.discard(key)
            callback = kwargs.get("on_click")
            if callable(callback):
                callback(*kwargs.get("args", ()), **kwargs.get("kwargs", {}))
        return clicked

    def link_button(self, *args: Any, **kwargs: Any) -> DummyElement:
        self.events.append({"kind": "link_button", "args": args, "kwargs": kwargs})
        return DummyElement(self)

    def download_button(self, *args: Any, **kwargs: Any) -> bool:
        api = self.api if isinstance(self, DummyElement) else self
        if api is not None:
            api.events.append({"kind": "download_button", "args": args, "kwargs": kwargs})
        return False

    def form_submit_button(self, *args: Any, **kwargs: Any) -> bool:
        return self.button(*args, **kwargs)

    def text_input(self, label: str = "", value: str = "", *, key: str | None = None, **kwargs: Any) -> str:
        return str(self._state_value(key, value))

    def text_area(self, label: str = "", value: str = "", *, key: str | None = None, **kwargs: Any) -> str:
        return str(self._state_value(key, value))

    def number_input(self, label: str = "", *, value: Any = "min", key: str | None = None, **kwargs: Any) -> Any:
        self.events.append({"kind": "number_input", "args": (label,), "kwargs": {"value": value, "key": key, **kwargs}})
        numeric = [v for v in (value, kwargs.get("min_value"), kwargs.get("max_value"), kwargs.get("step")) if v is not None and v != "min"]
        if self.strict_numeric:
            kinds = {type(v) for v in numeric}
            if len(kinds) > 1 or not kinds.issubset({int, float}):
                raise TypeError("Streamlit numeric contract: value/min/max/step types must match")
        default = kwargs.get("min_value", 0.0 if any(isinstance(v, float) for v in numeric) else 0) if value == "min" else value
        return self._state_value(key, default)

    def date_input(self, label: str = "", value: Any = None, *, key: str | None = None, **kwargs: Any) -> Any:
        return self._state_value(key, value if value is not None else date.today())

    def time_input(self, label: str = "", value: Any = None, *, key: str | None = None, **kwargs: Any) -> Any:
        return self._state_value(key, value)

    def selectbox(self, label: str, options: Iterable[Any], *, index: int | None = 0, key: str | None = None, **kwargs: Any) -> Any:
        choices = list(options)
        default = None if index is None else choices[index or 0]
        return self._state_value(key, default)

    def radio(self, label: str, options: Iterable[Any], *, index: int | None = 0, key: str | None = None, **kwargs: Any) -> Any:
        return self.selectbox(label, options, index=index, key=key)

    def multiselect(self, label: str, options: Iterable[Any], *, default: Any = None, key: str | None = None, **kwargs: Any) -> list[Any]:
        initial = list(default or [])
        return list(self._state_value(key, initial))

    def checkbox(self, label: str, value: bool = False, *, key: str | None = None, **kwargs: Any) -> bool:
        return bool(self._state_value(key, value))

    def toggle(self, label: str, value: bool = False, *, key: str | None = None, **kwargs: Any) -> bool:
        return self.checkbox(label, value, key=key)

    def slider(self, label: str, *args: Any, value: Any = None, key: str | None = None, **kwargs: Any) -> Any:
        if value is None and args:
            value = args[-1]
        return self._state_value(key, value)

    def select_slider(self, label: str, *, options: Iterable[Any], value: Any = None, key: str | None = None, **kwargs: Any) -> Any:
        choices = list(options)
        return self._state_value(key, value if value is not None else choices[0])

    def data_editor(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        api = self.api if isinstance(self, DummyElement) else self
        if api is not None:
            api.events.append({"kind": "data_editor", "args": args, "kwargs": kwargs})
            data = api.edited_tables.get(kwargs.get("key"), data)
        return data.copy() if hasattr(data, "copy") else data

    def file_uploader(self, *args: Any, **kwargs: Any) -> None:
        return None

    def dialog(self, *args: Any, **kwargs: Any):
        return lambda func: func

    def fragment(self, func=None, **kwargs: Any):
        if func is None:
            return lambda inner: inner
        return func

    def rerun(self, *args: Any, **kwargs: Any) -> None:
        return None

    def stop(self) -> None:
        return None

    def __getattr__(self, _name: str):
        def no_op(*args: Any, **kwargs: Any) -> DummyElement:
            self.events.append({"kind": _name, "args": args, "kwargs": kwargs})
            return DummyElement(self)
        return no_op


def install(*, strict_numeric: bool = False) -> types.ModuleType:
    """Install one adapter per process; never silently replace a real runtime."""
    existing = sys.modules.get("streamlit")
    if existing is not None and "_api" in existing.__dict__:
        existing._api.strict_numeric = existing._api.strict_numeric or strict_numeric
        return existing
    if existing is not None and existing.__dict__.get("__version__"):
        raise RuntimeError("Run adapter tests in a separate process from real Streamlit tests")
    api = StreamlitAPI()
    api.strict_numeric = strict_numeric
    module = types.ModuleType("streamlit")
    module.__dict__["_api"] = api
    for name in dir(api):
        if not name.startswith("_"):
            module.__dict__[name] = getattr(api, name)
    module.__dict__["session_state"] = api.session_state
    module.__dict__["secrets"] = api.secrets
    module.__dict__["query_params"] = api.query_params
    module.__dict__["sidebar"] = api.sidebar
    module.__dict__["column_config"] = api.column_config
    module.__dict__["cache_data"] = api.cache_data
    module.__dict__["cache_resource"] = api.cache_resource
    module.__dict__["__getattr__"] = api.__getattr__
    module.__path__ = []  # Mark as package for submodule imports.

    components = types.ModuleType("streamlit.components")
    components.__path__ = []
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *args, **kwargs: DummyElement(api)
    components.v1 = components_v1
    module.components = components

    runtime = types.ModuleType("streamlit.runtime")
    runtime.__path__ = []
    uploaded = types.ModuleType("streamlit.runtime.uploaded_file_manager")
    class UploadedFile:  # pragma: no cover - type compatibility only
        pass
    uploaded.UploadedFile = UploadedFile
    runtime.uploaded_file_manager = uploaded
    module.runtime = runtime

    sys.modules["streamlit"] = module
    sys.modules["streamlit.components"] = components
    sys.modules["streamlit.components.v1"] = components_v1
    sys.modules["streamlit.runtime"] = runtime
    sys.modules["streamlit.runtime.uploaded_file_manager"] = uploaded
    return module
