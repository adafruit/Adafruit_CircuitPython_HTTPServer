# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.route._HTTPRoute`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Callable, List, Union
except ImportError:
    pass

import re

from .methods import HTTPMethod


class _HTTPRoute:
    """Route definition for different paths, see `adafruit_httpserver.server.HTTPServer.route`."""

    def __init__(self, path: str = "", method: HTTPMethod = HTTPMethod.GET) -> None:

        contains_regex = re.search(r"<\w*>", path)

        self.path = path if not contains_regex else re.sub(r"<\w*>", r"([^/]*)", path)
        self.method = method
        self.regex = contains_regex

    def matches(self, other: "_HTTPRoute") -> bool:
        """
        Checks if the route matches the other route.

        If the route contains parameters, it will check if the other route contains values for them.
        """

        if self.regex or other.regex:
            return re.match(self.path, other.path) and self.method == other.method

        return self.method == other.method and self.path == other.path

    def __repr__(self) -> str:
        return f"HTTPRoute(path={repr(self.path)}, method={repr(self.method)})"


class _HTTPRoutes:
    """A collection of routes and their corresponding handlers."""

    def __init__(self) -> None:
        self._routes: List[_HTTPRoute] = []
        self._handlers: List[Callable] = []

    def add(self, route: _HTTPRoute, handler: Callable):
        """Adds a route and its handler to the collection."""

        self._routes.append(route)
        self._handlers.append(handler)

    def find_handler(self, route: _HTTPRoute) -> Union[Callable, None]:
        """
        Finds a handler for a given route.

        If route used URL parameters, the handler will be wrapped to pass the parameters to the
        handler.

        Example::

            @server.route("/example/<my_parameter>", HTTPMethod.GET)
            def route_func(request, my_parameter):
                ...
                request.path == "/example/123" # True
                my_parameter == "123" # True
        """

        try:
            matched_route = next(filter(lambda r: r.matches(route), self._routes))
        except StopIteration:
            return None

        handler = self._handlers[self._routes.index(matched_route)]
        args = re.match(matched_route.path, route.path).groups()

        def wrapper(request):
            return handler(request, *args)

        return wrapper
