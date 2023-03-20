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

        contains_regex = re.search(r"<\w*>", path) is not None

        self.path = path if not contains_regex else re.sub(r"<\w*>", r"([^/]*)", path)
        self.method = method
        self._contains_regex = contains_regex
        self._last_match_groups: Union[List[str], None] = None

    def matches(self, other: "_HTTPRoute") -> bool:
        """
        Checks if the route matches the other route.

        If the route contains parameters, it will check if the ``other`` route contains values for
        them.
        """
        if self.method != other.method:
            return False

        if not self._contains_regex:
            return self.path == other.path

        regex_match = re.match(self.path, other.path)
        if regex_match is None:
            return False

        self._last_match_groups = regex_match.groups()
        return True

    def last_match_groups(self) -> Union[List[str], None]:
        """
        Returns the last match groups from the last call to `matches`.

        Useful for getting the values of the parameters from the route, without the need to call
        `re.match` again.
        """
        return self._last_match_groups

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
        args = matched_route.last_match_groups() or []

        def wrapper(request):
            return handler(request, *args)

        return wrapper
