# SPDX-FileCopyrightText: Copyright (c) 2022 Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.headers`
====================================================
* Author(s): Michał Pokusa
"""

try:
    from typing import Dict, Tuple, Union
except ImportError:
    pass


class Headers:
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

    _storage: Dict[str, Tuple[str, str]]

    def __init__(self, headers: Union[str, Dict[str, str]] = None) -> None:
        if isinstance(headers, str):
            headers = {
                name: value
                for header_line in headers.strip().splitlines()
                for name, value in [header_line.split(": ", 1)]
            }
        else:
            headers = headers or {}

        self._storage = {key.lower(): [key, value] for key, value in headers.items()}

    def get(self, name: str, default: str = None) -> Union[str, None]:
        """Returns the value for the given header name, or default if not found."""
        return self._storage.get(name.lower(), [None, default])[1]

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

    def setdefault(self, name: str, default: str = None):
        """Sets the value for the given header name if it does not exist."""
        return self._storage.setdefault(name.lower(), [name, default])[1]

    def items(self):
        """Returns a list of (name, value) tuples."""
        return dict(self._storage.values()).items()

    def keys(self):
        """Returns a list of header names."""
        return list(dict(self._storage.values()).keys())

    def values(self):
        """Returns a list of header values."""
        return list(dict(self._storage.values()).values())

    def update(self, headers: Dict[str, str]):
        """Updates the headers with the given dict."""
        return self._storage.update(
            {key.lower(): [key, value] for key, value in headers.items()}
        )

    def copy(self):
        """Returns a copy of the headers."""
        return Headers(dict(self._storage.values()))

    def __getitem__(self, name: str):
        return self._storage[name.lower()][1]

    def __setitem__(self, name: str, value: str):
        self._storage[name.lower()] = [name, value]

    def __delitem__(self, name: str):
        del self._storage[name.lower()]

    def __iter__(self):
        return iter(dict(self._storage.values()))

    def __len__(self):
        return len(self._storage)

    def __contains__(self, key: str):
        return key.lower() in self._storage.keys()

    def __repr__(self):
        return f"{self.__class__.__name__}({dict(self._storage.values())})"
