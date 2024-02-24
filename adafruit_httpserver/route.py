# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.route`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Callable, Iterable, Union, Tuple, Literal, Dict, TYPE_CHECKING

    if TYPE_CHECKING:
        from .response import Response
except ImportError:
    pass

import re

from .methods import GET


class Route:
    """Route definition for different paths, see `adafruit_httpserver.server.Server.route`."""

    @staticmethod
    def _prepare_path_pattern(path: str, append_slash: bool) -> str:
        # Escape all dots
        path = re.sub(r"\.", r"\\.", path)

        # Replace url parameters with regex groups
        path = re.sub(r"<\w+>", r"([^/]+)", path)

        # Replace wildcards with corresponding regex
        path = path.replace(r"\.\.\.\.", r".+").replace(r"\.\.\.", r"[^/]+")

        # Add optional slash at the end if append_slash is True
        if append_slash:
            path += r"/?"

        # Add start and end of string anchors
        return f"^{path}$"

    def __init__(
        self,
        path: str = "",
        methods: Union[str, Iterable[str]] = GET,
        handler: Callable = None,
        *,
        append_slash: bool = False,
    ) -> None:
        self._validate_path(path, append_slash)

        self.path = path
        self.methods = (
            set(methods) if isinstance(methods, (set, list, tuple)) else set([methods])
        )
        self.handler = handler
        self.parameters_names = [
            name[1:-1] for name in re.compile(r"/[^<>]*/?").split(path) if name != ""
        ]
        self.path_pattern = re.compile(self._prepare_path_pattern(path, append_slash))

    @staticmethod
    def _validate_path(path: str, append_slash: bool) -> None:
        if not path.startswith("/"):
            raise ValueError("Path must start with a slash.")

        if path.endswith("/") and append_slash:
            raise ValueError("Cannot use append_slash=True when path ends with /")

        if "//" in path:
            raise ValueError("Path cannot contain double slashes.")

        if "<>" in path:
            raise ValueError("All URL parameters must be named.")

        if re.search(r"[^/]<[^/]+>|<[^/]+>[^/]", path):
            raise ValueError("All URL parameters must be between slashes.")

        if re.search(r"[^/.]\.\.\.\.?|\.?\.\.\.[^/.]", path):
            raise ValueError("... and .... must be between slashes")

        if "....." in path:
            raise ValueError("Path cannot contain more than 4 dots in a row.")

    def matches(
        self, method: str, path: str
    ) -> Union[Tuple[Literal[False], None], Tuple[Literal[True], Dict[str, str]]]:
        """
        Checks if the route matches given ``method`` and ``path``.

        If the route contains parameters, it will check if the ``path`` contains values for
        them.

        Returns tuple of a boolean that indicates if the routes matches and a dict containing
        values for url parameters.
        If the route does not match ``path`` or ``method`` if will return ``None`` instead of dict.

        Examples::

            route = Route("/example", GET, append_slash=True)

            route.matches(GET, "/example") # True, {}
            route.matches(GET, "/example/") # True, {}

            route.matches(GET, "/other-example") # False, None
            route.matches(POST, "/example/") # False, None

            ...

            route = Route("/example/<parameter>", GET)

            route.matches(GET, "/example/123") # True, {"parameter": "123"}

            route.matches(GET, "/other-example") # False, None

            ...

            route = Route("/example/.../something", GET)
            route.matches(GET, "/example/123/something") # True, {}

            route = Route("/example/..../something", GET)
            route.matches(GET, "/example/123/456/something") # True, {}
        """

        if method not in self.methods:
            return False, None

        path_match = self.path_pattern.match(path)
        if path_match is None:
            return False, None

        url_parameters_values = path_match.groups()

        return True, dict(zip(self.parameters_names, url_parameters_values))

    def __repr__(self) -> str:
        path = self.path
        methods = self.methods
        handler = self.handler

        return f"<Route {path=}, {methods=}, {handler=}>"


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
