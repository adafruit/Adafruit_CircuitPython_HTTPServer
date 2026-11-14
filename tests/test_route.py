# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Tests for adafruit_httpserver.Route, as_route() and Server route registration."""

import pytest

from adafruit_httpserver import DELETE, GET, POST, PUT, Route, Server, as_route


def handler(request):
    return None


def test_exact_path():
    route = Route("/example")

    assert route.matches(GET, "/example") == (True, {})
    assert route.matches(GET, "/example/") == (False, None)
    assert route.matches(GET, "/other") == (False, None)
    assert route.matches(GET, "/example/more") == (False, None)


def test_default_method_is_get():
    route = Route("/example")

    assert route.methods == {GET}
    assert route.matches(POST, "/example") == (False, None)


@pytest.mark.parametrize("methods", [POST, [GET, POST], (GET, POST), {GET, POST}])
def test_methods_forms(methods):
    route = Route("/example", methods)

    assert route.matches(POST, "/example") == (True, {})
    assert route.matches(DELETE, "/example") == (False, None)


def test_append_slash():
    route = Route("/example", append_slash=True)

    assert route.matches(GET, "/example") == (True, {})
    assert route.matches(GET, "/example/") == (True, {})
    assert route.matches(GET, "/example//") == (False, None)


def test_url_parameters():
    # From examples/httpserver_url_parameters.py
    route = Route("/device/<device_id>/action/<action>")

    assert route.parameters_names == ["device_id", "action"]
    assert route.matches(GET, "/device/42/action/turn_on") == (
        True,
        {"device_id": "42", "action": "turn_on"},
    )
    assert route.matches(GET, "/device/42/action") == (False, None)
    assert route.matches(GET, "/device/42/action/turn_on/extra") == (False, None)


def test_url_parameter_requires_non_empty_segment():
    route = Route("/device/<device_id>")

    assert route.matches(GET, "/device/") == (False, None)
    assert route.matches(GET, "/device/a/b") == (False, None)


def test_url_parameter_with_append_slash():
    route = Route("/file/<name>", append_slash=True)

    assert route.matches(GET, "/file/abc") == (True, {"name": "abc"})
    assert route.matches(GET, "/file/abc/") == (True, {"name": "abc"})


def test_single_segment_wildcard():
    # From examples/httpserver_url_parameters.py
    route = Route("/device/.../status")

    assert route.matches(GET, "/device/123/status") == (True, {})
    assert route.matches(GET, "/device/123/456/status") == (False, None)
    assert route.matches(GET, "/device//status") == (False, None)


def test_multi_segment_wildcard():
    route = Route("/device/....")

    assert route.matches(GET, "/device/123") == (True, {})
    assert route.matches(GET, "/device/123/456/status") == (True, {})
    assert route.matches(GET, "/device/") == (False, None)


def test_wildcard_with_url_parameter():
    route = Route("/a/.../<x>")

    assert route.parameters_names == ["x"]
    assert route.matches(GET, "/a/anything/2") == (True, {"x": "2"})


def test_dot_is_literal():
    route = Route("/file.txt")

    assert route.matches(GET, "/file.txt") == (True, {})
    assert route.matches(GET, "/fileXtxt") == (False, None)


@pytest.mark.xfail(
    strict=True,
    reason="Route escapes only '.' in a path. Other regex characters, such as '+', act as regex "
    "syntax.",
)
def test_regex_characters_are_literal():
    route = Route("/a+b")

    assert route.matches(GET, "/a+b") == (True, {})
    assert route.matches(GET, "/aab") == (False, None)


@pytest.mark.parametrize(
    ("path", "append_slash", "message"),
    [
        ("example", False, "Path must start with a slash."),
        ("/example/", True, "Cannot use append_slash=True when path ends with /"),
        ("/a//b", False, "Path cannot contain double slashes."),
        ("/a/<>", False, "All URL parameters must be named."),
        ("/a<b>", False, "All URL parameters must be between slashes."),
        ("/<b>c", False, "All URL parameters must be between slashes."),
        ("/a...", False, "... and .... must be between slashes"),
        ("/....a", False, "... and .... must be between slashes"),
        ("/a/.....", False, "Path cannot contain more than 4 dots in a row."),
    ],
)
def test_invalid_paths(path, append_slash, message):
    with pytest.raises(ValueError, match=f"^{message.replace('.', '[.]')}$"):
        Route(path, append_slash=append_slash)


@pytest.mark.xfail(
    strict=True,
    reason="Parameter names with non-word characters are accepted but the route never matches",
)
def test_parameter_name_with_non_word_characters():
    try:
        route = Route("/a/<b-c>")
    except ValueError:
        return  # Rejecting the name is also correct.

    assert route.matches(GET, "/a/x") == (True, {"b-c": "x"})


def test_repr():
    route = Route("/x", GET, handler)

    assert repr(route) == f"<Route path='/x', methods={{'GET'}}, handler={handler!r}>"


def test_as_route():
    @as_route("/example", [GET, POST], append_slash=True)
    def example(request):
        return "response"

    assert isinstance(example, Route)
    assert example.path == "/example"
    assert example.methods == {GET, POST}
    assert example.matches(GET, "/example/") == (True, {})
    assert example.handler(None) == "response"


def test_as_route_twice_raises():
    with pytest.raises(ValueError, match="as_route can be used only once per function"):

        @as_route("/one")
        @as_route("/two")
        def example(request):
            pass


def test_as_route_invalid_path_raises():
    with pytest.raises(ValueError, match="Path must start with a slash"):

        @as_route("no-slash")
        def example(request):
            pass


def test_server_route_decorator_returns_function_so_it_can_be_stacked(fake_pool):
    # Stacked decorators as in examples/httpserver_url_parameters.py
    server = Server(fake_pool())

    @server.route("/device/<device_id>/action/<action>")
    @server.route("/device/emergency-power-off/<device_id>")
    def perform_action(request, device_id, action="emergency_power_off"):
        return (device_id, action)

    assert callable(perform_action)
    assert not isinstance(perform_action, Route)

    assert server._find_handler(GET, "/device/7/action/turn_on")(None) == ("7", "turn_on")
    assert server._find_handler(GET, "/device/emergency-power-off/7")(None) == (
        "7",
        "emergency_power_off",
    )
    assert server._find_handler(POST, "/device/7/action/turn_on") is None


def test_server_add_routes(fake_pool):
    server = Server(fake_pool())

    @as_route("/decorated", PUT)
    def decorated(request):
        return "decorated"

    server.add_routes([Route("/plain", GET, lambda request: "plain"), decorated])

    assert server._find_handler(GET, "/plain")(None) == "plain"
    assert server._find_handler(PUT, "/decorated")(None) == "decorated"
    assert server._find_handler(GET, "/decorated") is None


def test_server_first_matching_route_wins(fake_pool):
    server = Server(fake_pool())

    @server.route("/device/<device_id>")
    def specific(request, device_id):
        return "parameter"

    @server.route("/device/....")
    def wildcard(request):
        return "wildcard"

    assert server._find_handler(GET, "/device/1")(None) == "parameter"
    assert server._find_handler(GET, "/device/1/2")(None) == "wildcard"
