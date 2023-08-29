# SPDX-FileCopyrightText: Copyright (c) 2022 Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.headers`
====================================================
* Author(s): Michał Pokusa
"""

try:
    from typing import Dict, List, Union
except ImportError:
    pass

from .interfaces import _IFieldStorage


class Headers(_IFieldStorage):
    """
    A dict-like class for storing HTTP headers.

    Allows access to headers using **case insensitive** names.

    Does **not** implement all dict methods.

    Examples::

        headers = Headers("Content-Type: text/html\\r\\nContent-Length: 1024\\r\\n")
        # or
        headers = Headers({"Content-Type": "text/html", "Content-Length": "1024"})

        len(headers)
        # 2

        headers.setdefault("Access-Control-Allow-Origin", "*")
        headers["Access-Control-Allow-Origin"]
        # '*'

        headers["Content-Length"]
        # '1024'

        headers["content-type"]
        # 'text/html'

        headers["User-Agent"]
        # KeyError: User-Agent

        "CONTENT-TYPE" in headers
        # True
    """

    _storage: Dict[str, List[str]]

    def __init__(self, headers: Union[str, Dict[str, str]] = None) -> None:
        self._storage = {}

        if isinstance(headers, str):
            for header_line in headers.strip().splitlines():
                name, value = header_line.split(": ", 1)
                self.add(name, value)
        else:
            for key, value in (headers or {}).items():
                self.add(key, value)

    def add(self, field_name: str, value: str):
        """
        Adds a header with the given field name and value.
        Allows adding multiple headers with the same name.
        """
        self._add_field_value(field_name.lower(), value)

    def get(self, field_name: str, default: str = None) -> Union[str, None]:
        """Returns the value for the given header name, or default if not found."""
        return super().get(field_name.lower(), default)

    def get_list(self, field_name: str) -> List[str]:
        """Get the list of values of a field."""
        return super().get_list(field_name.lower())

    def get_directive(self, name: str, default: str = None) -> Union[str, None]:
        """
        Returns the main value (directive) for the given header name, or default if not found.

        Example::

            headers = Headers({"Content-Type": "text/html; charset=utf-8"})
            headers.get_directive("Content-Type")
            # 'text/html'
        """

        header_value = self.get(name)
        if header_value is None:
            return default
        return header_value.split(";")[0].strip('" ')

    def get_parameter(
        self, name: str, parameter: str, default: str = None
    ) -> Union[str, None]:
        """
        Returns the value of the given parameter for the given header name, or default if not found.

        Example::

            headers = Headers({"Content-Type": "text/html; charset=utf-8"})
            headers.get_parameter("Content-Type", "charset")
            # 'utf-8'
        """

        header_value = self.get(name)
        if header_value is None:
            return default
        for header_parameter in header_value.split(";"):
            if header_parameter.strip().startswith(parameter):
                return header_parameter.strip().split("=")[1].strip('" ')
        return default

    def set(self, name: str, value: str):
        """Sets the value for the given header name."""
        self._storage[name.lower()] = [value]

    def setdefault(self, name: str, default: str = None):
        """Sets the value for the given header name if it does not exist."""
        return self._storage.setdefault(name.lower(), [default])

    def update(self, headers: Dict[str, str]):
        """Updates the headers with the given dict."""
        return self._storage.update(
            {key.lower(): [value] for key, value in headers.items()}
        )

    def copy(self):
        """Returns a copy of the headers."""
        return Headers(
            "\r\n".join(
                f"{key}: {value}" for key in self.fields for value in self.get_list(key)
            )
        )

    def __getitem__(self, name: str):
        return super().__getitem__(name.lower())

    def __setitem__(self, name: str, value: str):
        self._storage[name.lower()] = [value]

    def __delitem__(self, name: str):
        del self._storage[name.lower()]

    def __contains__(self, key: str):
        return super().__contains__(key.lower())
