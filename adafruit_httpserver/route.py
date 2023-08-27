# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.route`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Callable, List, Iterable, Union, Tuple, Dict, TYPE_CHECKING

    if TYPE_CHECKING:
        from .response import Response
except ImportError:
    pass

import re

from .methods import GET


class Route:
    """Route definition for different paths, see `adafruit_httpserver.server.Server.route`."""

    def __init__(
        self,
        path: str = "",
        methods: Union[str, Iterable[str]] = GET,
        handler: Callable = None,
        *,
        append_slash: bool = False,
    ) -> None:
        self._validate_path(path, append_slash)

        self.parameters_names = [
            name[1:-1] for name in re.compile(r"/[^<>]*/?").split(path) if name != ""
        ]
        self.path = re.sub(r"<\w+>", r"([^/]+)", path).replace("....", r".+").replace(
            "...", r"[^/]+"
        ) + ("/?" if append_slash else "")
        self.methods = (
            set(methods) if isinstance(methods, (set, list, tuple)) else set([methods])
        )

        self.handler = handler

    @staticmethod
    def _validate_path(path: str, append_slash: bool) -> None:
        if not path.startswith("/"):
            raise ValueError("Path must start with a slash.")

        if "<>" in path:
            raise ValueError("All URL parameters must be named.")

        if path.endswith("/") and append_slash:
            raise ValueError("Cannot use append_slash=True when path ends with /")

    def match(self, other: "Route") -> Tuple[bool, Dict[str, str]]:
        """
        Checks if the route matches the other route.

        If the route contains parameters, it will check if the ``other`` route contains values for
        them.

        Returns tuple of a boolean and a list of strings. The boolean indicates if the routes match,
        and the list contains the values of the url parameters from the ``other`` route.

        Examples::

            route = Route("/example", GET, True)

            other1a = Route("/example", GET)
            other1b = Route("/example/", GET)
            route.matches(other1a) # True, {}
            route.matches(other1b) # True, {}

            other2 = Route("/other-example", GET)
            route.matches(other2) # False, {}

            ...

            route = Route("/example/<parameter>", GET)

            other1 = Route("/example/123", GET)
            route.matches(other1) # True, {"parameter": "123"}

            other2 = Route("/other-example", GET)
            route.matches(other2) # False, {}

            ...

            route1 = Route("/example/.../something", GET)
            other1 = Route("/example/123/something", GET)
            route1.matches(other1) # True, {}

            route2 = Route("/example/..../something", GET)
            other2 = Route("/example/123/456/something", GET)
            route2.matches(other2) # True, {}
        """

        if not other.methods.issubset(self.methods):
            return False, {}

        regex_match = re.match(f"^{self.path}$", other.path)
        if regex_match is None:
            return False, {}

        return True, dict(zip(self.parameters_names, regex_match.groups()))

    def __repr__(self) -> str:
        path = repr(self.path)
        methods = repr(self.methods)
        handler = repr(self.handler)

        return f"Route({path=}, {methods=}, {handler=})"


def as_route(
    path: str,
    methods: Union[str, Iterable[str]] = GET,
    *,
    append_slash: bool = False,
) -> "Callable[[Callable[..., Response]], Route]":
    """
    Decorator used to convert a function into a ``Route`` object.

    ``as_route`` can be only used once per function, because it replaces the function with
    a ``Route`` object that has the same name as the function.

    Later it can be imported and registered in the ``Server``.

    :param str path: URL path
    :param str methods: HTTP method(s): ``"GET"``, ``"POST"``, ``["GET", "POST"]`` etc.
    :param bool append_slash: If True, the route will be accessible with and without a
        trailing slash

    Example::

        # Converts a function into a Route object
        @as_route("/example")
        def some_func(request):
            ...

        some_func  # Route(path="/example", methods={"GET"}, handler=<function some_func at 0x...>)

        # WRONG: as_route can be used only once per function
        @as_route("/wrong-example1")
        @as_route("/wrong-example2")
        def wrong_func2(request):
            ...

        # If a route is in another file, you can import it and register it to the server

        from .routes import some_func

        ...

        server.add_routes([
            some_func,
        ])
    """

    def route_decorator(func: Callable) -> Route:
        if isinstance(func, Route):
            raise ValueError("as_route can be used only once per function.")

        return Route(path, methods, func, append_slash=append_slash)

    return route_decorator


class _Routes:
    """A collection of routes and their corresponding handlers."""

    def __init__(self) -> None:
        self._routes: List[Route] = []

    def add(self, route: Route):
        """Adds a route and its handler to the collection."""
        self._routes.append(route)

    def find_handler(self, route: Route) -> Union[Callable["...", "Response"], None]:
        """
        Finds a handler for a given route.

        If route used URL parameters, the handler will be wrapped to pass the parameters to the
        handler.

        Example::

            @server.route("/example/<my_parameter>", GET)
            def route_func(request, my_parameter):
                ...
                request.path == "/example/123" # True
                my_parameter == "123" # True
        """
        found_route, _route = False, None

        for _route in self._routes:
            matches, keyword_parameters = _route.match(route)

            if matches:
                found_route = True
                break

        if not found_route:
            return None

        handler = _route.handler

        def wrapped_handler(request):
            return handler(request, **keyword_parameters)

        return wrapped_handler

    def __repr__(self) -> str:
        return f"_Routes({repr(self._routes)})"
