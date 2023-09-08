# SPDX-FileCopyrightText: Copyright (c) 2023 Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.interfaces`
====================================================
* Author(s): Michał Pokusa
"""

try:
    from typing import List, Dict, Union, Any
except ImportError:
    pass


class _IFieldStorage:
    """Interface with shared methods for QueryParams, FormData and Headers."""

    _storage: Dict[str, List[Any]]

    def _add_field_value(self, field_name: str, value: Any) -> None:
        if field_name not in self._storage:
            self._storage[field_name] = [value]
        else:
            self._storage[field_name].append(value)

    def get(self, field_name: str, default: Any = None) -> Union[Any, None]:
        """Get the value of a field."""
        return self._storage.get(field_name, [default])[0]

    def get_list(self, field_name: str) -> List[Any]:
        """Get the list of values of a field."""
        return self._storage.get(field_name, [])

    @property
    def fields(self):
        """Returns a list of field names."""
        return list(self._storage.keys())

    def items(self):
        """Returns a list of (name, value) tuples."""
        return [(key, value) for key in self.fields for value in self.get_list(key)]

    def keys(self):
        """Returns a list of header names."""
        return self.fields

    def values(self):
        """Returns a list of header values."""
        return [value for key in self.keys() for value in self.get_list(key)]

    def __getitem__(self, field_name: str):
        return self._storage[field_name][0]

    def __iter__(self):
        return iter(self._storage)

    def __len__(self) -> int:
        return len(self._storage)

    def __contains__(self, key: str) -> bool:
        return key in self._storage

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self._storage)})"


def _encode_html_entities(value: Union[str, None]) -> Union[str, None]:
    """Encodes unsafe HTML characters that could enable XSS attacks."""
    if value is None:
        return None

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class _IXSSSafeFieldStorage(_IFieldStorage):
    def get(
        self, field_name: str, default: Any = None, *, safe=True
    ) -> Union[Any, None]:
        if safe:
            return _encode_html_entities(super().get(field_name, default))

        _debug_warning_nonencoded_output()
        return super().get(field_name, default)

    def get_list(self, field_name: str, *, safe=True) -> List[Any]:
        if safe:
            return [
                _encode_html_entities(value) for value in super().get_list(field_name)
            ]

        _debug_warning_nonencoded_output()
        return super().get_list(field_name)


def _debug_warning_nonencoded_output():
    """Warns about XSS risks."""
    print(
        "WARNING: Setting safe to False makes XSS vulnerabilities possible by "
        "allowing access to raw untrusted values submitted by users. If this data is reflected "
        "or shown within HTML without proper encoding it could enable Cross-Site Scripting."
    )
