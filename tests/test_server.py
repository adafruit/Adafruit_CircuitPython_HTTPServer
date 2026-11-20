# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
End-to-end tests for adafruit_httpserver.Server.

Most tests use real CPython sockets on 127.0.0.1 (``make_server`` and ``http`` fixtures),
with routes modeled on the examples. Error paths that are hard to cause with real sockets
use ``fake_pool``.
"""

import errno
import json
import re
import socket
import ssl
import threading
import time

import pytest

from adafruit_httpserver import (
    CONNECTION_TIMED_OUT,
    DELETE,
    GET,
    NO_REQUEST,
    NOT_FOUND_404,
    POST,
    PUT,
    REQUEST_HANDLED_NO_RESPONSE,
    REQUEST_HANDLED_RESPONSE_SENT,
    Basic,
    Bearer,
    ChunkedResponse,
    Headers,
    JSONResponse,
    Redirect,
    Response,
    Server,
    ServerStoppedError,
    Token,
    check_authentication,
    require_authentication,
)
from adafruit_httpserver.status import UNAUTHORIZED_401


def get(path, headers=None):
    lines = [f"GET {path} HTTP/1.1", "Host: localhost"]
    lines += [f"{name}: {value}" for name, value in (headers or {}).items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def request_with_body(method, path, body, content_type=None, headers=None):
    lines = [f"{method} {path} HTTP/1.1", "Host: localhost", f"Content-Length: {len(body)}"]
    if content_type is not None:
        lines.append(f"Content-Type: {content_type}")
    lines += [f"{name}: {value}" for name, value in (headers or {}).items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


def poll_until_request(server, timeout=5):
    """Poll until something other than NO_REQUEST happens, for tests with a client thread."""
    deadline = time.monotonic() + timeout
    while (result := server.poll()) == NO_REQUEST:
        assert time.monotonic() < deadline, "no request arrived"
        time.sleep(0.01)
    return result


@pytest.fixture
def www(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Home</h1>")
    (tmp_path / "style.css").write_text("body {}")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "index.html").write_text("<h1>Sub</h1>")
    return tmp_path


# poll() results


def test_poll_no_request(make_server):
    server = make_server()

    assert server.poll() == NO_REQUEST


def test_poll_response_sent(make_server, http):
    # From examples/httpserver_cpython.py
    server = make_server()

    @server.route("/")
    def base(request):
        return Response(request, "Hello from the CircuitPython HTTP Server!")

    result, reply = http(server, get("/"))

    assert result == REQUEST_HANDLED_RESPONSE_SENT
    assert reply.status_line == "HTTP/1.1 200 OK"
    assert reply.body == b"Hello from the CircuitPython HTTP Server!"


def test_poll_handler_returns_none(make_server, http):
    server = make_server()
    handled = []

    @server.route("/")
    def no_response(request):
        handled.append(request.path)

    result, reply = http(server, get("/"))

    assert result == REQUEST_HANDLED_NO_RESPONSE
    assert reply is None
    assert handled == ["/"]


def test_poll_client_sends_nothing_and_closes(make_server, http):
    server = make_server()

    result, reply = http(server, b"", shutdown=True)

    assert result == CONNECTION_TIMED_OUT
    assert reply is None


def test_poll_client_sends_nothing_and_waits(make_server, http):
    server = make_server()
    server.socket_timeout = 0.2

    result, reply = http(server, b"")

    assert result == CONNECTION_TIMED_OUT
    assert reply is None


def test_poll_when_stopped(fake_pool, make_server):
    with pytest.raises(ServerStoppedError):
        Server(fake_pool()).poll()

    server = make_server()
    server.stop()
    with pytest.raises(ServerStoppedError):
        server.poll()


# Routing, modeled on the examples


def test_url_parameters(make_server, http):
    # From examples/httpserver_url_parameters.py
    server = make_server()

    @server.route("/device/<device_id>/action/<action>")
    @server.route("/device/emergency-power-off/<device_id>")
    def perform_action(request, device_id, action="emergency_power_off"):
        return Response(request, f"Action ({action}) performed on device with ID: {device_id}")

    @server.route("/device/<device_id>/status/<date>")
    def device_status_on_date(request, **params):
        return Response(request, f"Status of {params['device_id']} on {params['date']}: ...")

    @server.route("/device/.../status", append_slash=True)
    @server.route("/device/....", append_slash=True)
    def device_status(request):
        return Response(request, "Status of all devices: ...")

    expected = {
        "/device/1/action/turn_on": b"Action (turn_on) performed on device with ID: 1",
        "/device/emergency-power-off/2": (
            b"Action (emergency_power_off) performed on device with ID: 2"
        ),
        "/device/3/status/2024-01-01": b"Status of 3 on 2024-01-01: ...",
        "/device/4/status/": b"Status of all devices: ...",
        "/device/anything/else/here": b"Status of all devices: ...",
    }
    for path, body in expected.items():
        _, reply = http(server, get(path))
        assert reply.body == body, path


def test_methods_json_api(make_server, http):
    # Based on examples/httpserver_methods.py
    server = make_server()
    objects = [{"id": 1, "name": "Object 1"}]

    @server.route("/api", [GET, POST, PUT, DELETE], append_slash=True)
    def api(request):
        if request.method == GET:
            return JSONResponse(request, objects)
        uploaded = request.json()
        if request.method in {POST, PUT}:
            objects[:] = [obj for obj in objects if obj["id"] != uploaded["id"]] + [uploaded]
            return JSONResponse(request, {"message": "Object saved", "object": uploaded})
        objects[:] = [obj for obj in objects if obj["id"] != uploaded["id"]]
        return JSONResponse(request, {"message": "Object deleted", "object": uploaded})

    _, reply = http(server, get("/api/"))
    assert reply.header("Content-Type") == "application/json"
    assert json.loads(reply.body) == [{"id": 1, "name": "Object 1"}]

    _, reply = http(server, request_with_body(POST, "/api", b'{"id": 2, "name": "Two"}'))
    assert json.loads(reply.body)["message"] == "Object saved"

    _, reply = http(server, request_with_body(DELETE, "/api", b'{"id": 1}'))
    assert json.loads(reply.body)["message"] == "Object deleted"

    _, reply = http(server, get("/api"))
    assert json.loads(reply.body) == [{"id": 2, "name": "Two"}]


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        ("application/x-www-form-urlencoded", b"something=typed"),
        ("text/plain", b"something=typed\r\n"),
        (
            "multipart/form-data; boundary=----b",
            b'------b\r\nContent-Disposition: form-data; name="something"\r\n\r\n'
            b"typed\r\n------b--\r\n",
        ),
    ],
    ids=["urlencoded", "text-plain", "multipart"],
)
def test_form_data(make_server, http, content_type, body):
    # Based on examples/httpserver_form_data.py
    server = make_server()

    @server.route("/form", [GET, POST])
    def form(request):
        enctype = request.query_params.get("enctype", "text/plain")
        value = request.form_data.get("something") if request.method == POST else None
        return Response(request, f"{enctype}: {value}", content_type="text/html")

    _, reply = http(server, request_with_body(POST, "/form?enctype=x", body, content_type))

    assert reply.body == b"x: typed"


def test_cookies(make_server, http):
    # Based on examples/httpserver_cookies.py
    server = make_server()

    @server.route("/", GET)
    def themed_from_cookie(request):
        user_theme = request.cookies.get("theme", "light")
        wanted_theme = request.query_params.get("theme", user_theme)
        headers = Headers()
        headers.add("Set-Cookie", "cookie1=value1")
        return Response(
            request,
            wanted_theme,
            headers=headers,
            cookies={} if user_theme == wanted_theme else {"theme": wanted_theme},
        )

    _, reply = http(server, get("/?theme=dark"))
    assert reply.body == b"dark"
    assert sorted(reply.headers["set-cookie"]) == ["cookie1=value1", "theme=dark"]

    _, reply = http(server, get("/", {"Cookie": "theme=dark"}))
    assert reply.body == b"dark"
    assert reply.headers["set-cookie"] == ["cookie1=value1"]


def test_redirects(make_server, http):
    # Based on examples/httpserver_redirects.py
    server = make_server()
    redirects = {"adafruit": "https://www.adafruit.com"}

    @server.route("/blinka")
    def redirect_blinka(request):
        return Redirect(request, "https://circuitpython.org/blinka", permanent=True)

    @server.route("/login", POST)
    def temporary_login_redirect(request):
        return Redirect(request, "/fake-login", preserve_method=True)

    @server.route("/<slug>")
    def redirect_other(request, slug=None):
        if slug not in redirects:
            return Response(request, "Unknown redirect", status=NOT_FOUND_404)
        return Redirect(request, redirects[slug])

    _, reply = http(server, get("/blinka"))
    assert (reply.status, reply.header("Location")) == (301, "https://circuitpython.org/blinka")

    _, reply = http(server, request_with_body(POST, "/login", b"user=x"))
    assert (reply.status, reply.header("Location")) == (307, "/fake-login")

    _, reply = http(server, get("/adafruit"))
    assert (reply.status, reply.header("Location")) == (302, "https://www.adafruit.com")

    _, reply = http(server, get("/nope"))
    assert (reply.status, reply.body) == (404, b"Unknown redirect")


def test_chunked(make_server, http):
    # From examples/httpserver_chunked.py
    server = make_server()

    @server.route("/chunked")
    def chunked(request):
        def body():
            yield "Adaf"
            yield b"ruit"
            yield " Indus"
            yield b"tr"
            yield "ies"

        return ChunkedResponse(request, body)

    _, reply = http(server, get("/chunked"))

    assert reply.header("Transfer-Encoding") == "chunked"
    assert (
        reply.body == b"4\r\nAdaf\r\n4\r\nruit\r\n6\r\n Indus\r\n2\r\ntr\r\n3\r\nies\r\n0\r\n\r\n"
    )


def test_first_matching_route_wins(make_server, http):
    server = make_server()

    @server.route("/item/<item_id>")
    def specific(request, item_id):
        return Response(request, "specific")

    @server.route("/item/...")
    def wildcard(request):
        return Response(request, "wildcard")

    assert http(server, get("/item/1"))[1].body == b"specific"


def test_query_string_is_not_part_of_path(make_server, http):
    server = make_server()

    @server.route("/search")
    def search(request):
        return Response(request, request.query_params.get("q"))

    assert http(server, get("/search?q=abc"))[1].body == b"abc"


def test_multiple_servers(make_server, http, port_of):
    # Based on examples/httpserver_multiple_servers.py
    bedroom = make_server()
    office = make_server()

    @bedroom.route("/bedroom")
    def bedroom_route(request):
        return Response(request, "Hello from the bedroom!")

    @office.route("/office")
    def office_route(request):
        return Response(request, "Hello from the office!")

    assert port_of(bedroom) != port_of(office)
    assert http(bedroom, get("/bedroom"))[1].body == b"Hello from the bedroom!"
    assert http(office, get("/office"))[1].body == b"Hello from the office!"
    assert http(office, get("/bedroom"))[1].status == 404


# No route: file serving or 404


def test_no_route_and_no_root_path_is_404(make_server, http):
    server = make_server()

    _, reply = http(server, get("/missing"))

    assert reply.status == 404
    assert reply.body == b"File not found"


@pytest.mark.xfail(
    strict=True,
    reason="In debug mode, a request with no route and no root_path gets a 404 with an empty "
    "body. The body is the error's message, and ServingFilesDisabledError is raised without one.",
)
def test_no_route_and_no_root_path_debug_body(make_server, http):
    server = make_server(debug=True)

    _, reply = http(server, get("/missing"))

    assert reply.status == 404
    assert reply.body != b""


@pytest.mark.xfail(
    strict=True,
    reason="A path that matches a route but not its method gets 404. RFC 9110 section 15.5.6 "
    "calls for 405, with an Allow header listing the route's methods.",
)
def test_route_method_mismatch_is_405(make_server, http):
    server = make_server()

    @server.route("/only-post", POST)
    def only_post(request):
        return Response(request, "posted")

    _, reply = http(server, get("/only-post"))

    assert reply.status == 405
    assert reply.header("Allow") == "POST"


def test_static_files(make_server, http, www):
    # Based on examples/httpserver_static_files_serving.py
    server = make_server(str(www))

    _, reply = http(server, get("/"))
    assert (reply.status, reply.header("Content-Type"), reply.body) == (
        200,
        "text/html",
        b"<h1>Home</h1>",
    )

    _, reply = http(server, get("/style.css?v=2"))
    assert (reply.header("Content-Type"), reply.body) == ("text/css", b"body {}")

    _, reply = http(server, get("/sub/"))
    assert reply.body == b"<h1>Sub</h1>"


def test_static_file_head(make_server, http, www):
    server = make_server(str(www))

    _, reply = http(server, b"HEAD /style.css HTTP/1.1\r\nHost: localhost\r\n\r\n")

    assert reply.status == 200
    assert reply.header("Content-Length") == "7"
    assert reply.body == b""


def test_route_takes_precedence_over_file(make_server, http, www):
    server = make_server(str(www))

    @server.route("/style.css")
    def generated(request):
        return Response(request, "generated", content_type="text/css")

    assert http(server, get("/style.css"))[1].body == b"generated"


@pytest.mark.parametrize(
    ("path", "status", "body"),
    [
        ("/missing.html", 404, b"File not found"),
        ("/sub", 404, b"File not found"),
        ("/../secret.txt", 403, b"Invalid path"),
        ("/sub/..", 403, b"Invalid path"),
        ("/sub\\index.html", 403, b"Invalid path"),
    ],
)
def test_static_file_errors(make_server, http, www, path, status, body):
    server = make_server(str(www))

    _, reply = http(server, get(path))

    assert (reply.status, reply.body) == (status, body)


def test_static_file_error_details_in_debug_mode(make_server, http, www, capsys):
    server = make_server(str(www), debug=True)

    assert http(server, get("/../x"))[1].body == b"Parent directory reference in path: /../x"
    assert http(server, get("/nope"))[1].body == f"File does not exist: {www}/nope".encode()


def test_post_to_static_path_is_400(make_server, http, www):
    server = make_server(str(www))

    _, reply = http(server, request_with_body(POST, "/style.css", b"x=1"))

    assert reply.status == 400


# Authentication


def test_server_wide_authentication(make_server, http, www):
    # Based on examples/httpserver_authentication_server.py
    server = make_server(str(www))
    server.require_authentication([Basic("user", "password"), Bearer("642ec696")])

    @server.route("/implicit-require")
    def implicit_require_authentication(request):
        return Response(request, body="Authenticated", content_type="text/plain")

    for path in ["/implicit-require", "/style.css"]:
        _, reply = http(server, get(path))
        assert reply.status == 401
        assert reply.header("WWW-Authenticate") == 'Basic charset="UTF-8"'

        _, reply = http(server, get(path, {"Authorization": str(Basic("user", "wrong"))}))
        assert reply.status == 401

        _, reply = http(server, get(path, {"Authorization": str(Basic("user", "password"))}))
        assert reply.status == 200

        _, reply = http(server, get(path, {"Authorization": "Bearer 642ec696"}))
        assert reply.status == 200


def test_handler_authentication(make_server, http):
    # Based on examples/httpserver_authentication_handlers.py
    server = make_server()
    auths = [Basic("user", "password"), Token("2db53340")]

    @server.route("/check")
    def check_auth(request):
        if check_authentication(request, auths):
            return Response(request, "Authenticated")
        return Response(request, "Not authenticated", status=UNAUTHORIZED_401)

    @server.route("/require-or-401")
    def require_or_401(request):
        require_authentication(request, auths)
        return Response(request, "Authenticated")

    for path in ["/check", "/require-or-401"]:
        assert http(server, get(path))[1].status == 401
        _, reply = http(server, get(path, {"Authorization": "Token 2db53340"}))
        assert (reply.status, reply.body) == (200, b"Authenticated")


# Server default headers


def test_server_headers(make_server, http):
    server = make_server()
    server.headers = {"X-Server": "Adafruit CircuitPython HTTP Server", "X-Origin": "*"}

    @server.route("/")
    def handler(request):
        return Response(request, "x", headers={"X-Origin": "example.com"})

    _, reply = http(server, get("/"))
    assert reply.header("X-Server") == "Adafruit CircuitPython HTTP Server"
    assert reply.header("X-Origin") == "example.com"

    _, reply = http(server, get("/no-such-route"))
    assert reply.status == 404
    assert reply.header("X-Server") == "Adafruit CircuitPython HTTP Server"


def test_server_headers_setter_copies_headers_object(fake_pool):
    server = Server(fake_pool())
    headers = Headers({"X-A": "1"})

    server.headers = headers
    headers["X-A"] = "2"

    assert server.headers["X-A"] == "1"


# Handler errors and malformed requests


def test_handler_exception_is_raised_from_poll(make_server, http):
    server = make_server()

    @server.route("/")
    def broken(request):
        raise ZeroDivisionError("handler bug")

    with pytest.raises(ZeroDivisionError, match="handler bug"):
        http(server, get("/"))

    assert server.poll() == NO_REQUEST  # Server keeps working.


def test_handler_exception_traceback_in_debug_mode(make_server, http, capsys):
    server = make_server(debug=True)

    @server.route("/")
    def broken(request):
        raise ZeroDivisionError("handler bug")

    with pytest.raises(ZeroDivisionError):
        http(server, get("/"))

    assert "ZeroDivisionError: handler bug" in capsys.readouterr().err


@pytest.mark.xfail(
    strict=True,
    reason="An unparseable request makes poll() raise ValueError instead of answering 400",
)
def test_malformed_request_gets_400(make_server, http):
    server = make_server()

    result, reply = http(server, b"garbage\r\n\r\n")

    assert result == REQUEST_HANDLED_RESPONSE_SENT
    assert reply.status == 400


# Request size and timeouts


def test_body_larger_than_request_buffer(make_server, http):
    server = make_server()
    server.request_buffer_size = 64
    body = bytes(i % 251 for i in range(5000))

    @server.route("/echo", POST)
    def echo(request):
        return Response(request, request.body, content_type="application/octet-stream")

    _, reply = http(
        server,
        request_with_body(POST, "/echo", body, headers={"X-Long": "h" * 300}),
    )

    assert server.request_buffer_size == 64
    assert reply.body == body


def test_body_shorter_than_content_length(make_server, http):
    server = make_server()
    server.socket_timeout = 0.2

    @server.route("/echo", POST)
    def echo(request):
        return Response(request, request.body)

    raw = b"POST /echo HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nonly this"

    # Client waits: the server gives up after socket_timeout.
    assert http(server, raw)[1].body == b"only this"
    # Client closes its side: the server stops reading at end of input.
    assert http(server, raw, shutdown=True)[1].body == b"only this"


@pytest.mark.parametrize("value", [1, 0.5])
def test_socket_timeout_valid(fake_pool, value):
    server = Server(fake_pool())

    server.socket_timeout = value

    assert server.socket_timeout == value


@pytest.mark.parametrize("value", [0, -1, "1", None])
def test_socket_timeout_invalid(fake_pool, value):
    server = Server(fake_pool())

    with pytest.raises(ValueError, match="positive numeric value"):
        server.socket_timeout = value


# Starting and stopping


@pytest.mark.parametrize(("host", "port"), [(None, 80), ("127.0.0.1", None)])
def test_start_requires_host_and_port(fake_pool, host, port):
    with pytest.raises(RuntimeError, match="Host and port cannot be None"):
        Server(fake_pool()).start(host, port)


def test_start_unresolvable_host(fake_pool):
    server = Server(fake_pool(getaddrinfo_error=OSError(errno.EINVAL, "bad host")))

    with pytest.raises(RuntimeError, match="Cannot start server on bad.host:80"):
        server.start("bad.host", 80)
    assert server.stopped


def test_stop_and_restart(make_server, http):
    server = make_server()

    @server.route("/")
    def handler(request):
        return Response(request, "up")

    server.stop()
    assert server.stopped
    assert (server.host, server.port) == (None, None)

    server.start("127.0.0.1", 0)
    assert not server.stopped
    assert server.host == "127.0.0.1"
    assert http(server, get("/"))[1].body == b"up"


def test_repr(fake_pool):
    server = Server(fake_pool(), "/static")
    assert repr(server) == "<Server host=None, port=None, root_path='/static'>"

    server.start("127.0.0.1", 8080)
    assert repr(server) == "<Server host='127.0.0.1', port=8080, root_path='/static'>"


def test_debug_messages(make_server, http, capsys):
    server = make_server(debug=True)

    @server.route("/")
    def handler(request):
        return Response(request, "Hello")

    http(server, get("/?a=1"))
    server.stop()

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Started development server on http://127.0.0.1:0"
    assert re.fullmatch(r'127\.0\.0\.1 -- "GET /\?a=1" \d+ -- "200 OK" \d+ -- \d+ms', lines[1])
    assert lines[2] == "Stopped development server"


@pytest.mark.parametrize("root_path", ["", "/"])
def test_debug_warning_for_exposed_root_path(fake_pool, capsys, root_path):
    Server(fake_pool(), root_path, debug=True)

    assert "will expose all files on your device" in capsys.readouterr().out


def test_serve_forever_until_stopped():
    server = Server(socket)
    replies = []

    @server.route("/fail")
    def fail(request):
        raise RuntimeError("serve_forever ignores handler exceptions")

    @server.route("/stop")
    def stop(request):
        server.stop()
        return Response(request, "stopping")

    def client():
        try:
            deadline = time.monotonic() + 5
            while server._sock is None:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            address = ("127.0.0.1", server._sock.getsockname()[1])
            for path in ["/fail", "/stop"]:
                with socket.create_connection(address, timeout=5) as sock:
                    sock.sendall(get(path))
                    replies.append(sock.makefile("rb").read())
        finally:
            if not server.stopped:
                server.stop()  # Don't leave serve_forever() running if the client failed.

    thread = threading.Thread(target=client)
    thread.start()
    server.serve_forever("127.0.0.1", 0, poll_interval=0.01)
    thread.join()

    assert server.stopped
    assert replies[0] == b""
    assert replies[1].endswith(b"\r\n\r\nstopping")


def test_serve_forever_stops_on_keyboard_interrupt(fake_pool, fake_socket):
    reached_guard = []
    server = Server(fake_pool([fake_socket([get("/interrupt")]), fake_socket([get("/guard")])]))

    @server.route("/interrupt")
    def interrupt(request):
        raise KeyboardInterrupt

    @server.route("/guard")
    def guard(request):
        # Only reached if serve_forever() kept going; stop it so the test can't hang.
        reached_guard.append(True)
        server.stop()

    server.serve_forever("127.0.0.1", 80, poll_interval=0.01)

    assert server.stopped
    assert reached_guard == []


# Socket errors (fake sockets)


@pytest.mark.parametrize(
    "error",
    [
        OSError(errno.EAGAIN, "no connection"),
        ConnectionResetError(errno.ECONNRESET, "reset"),
        OSError(-30592, "MBEDTLS_ERR_SSL_FATAL_ALERT_MESSAGE"),
    ],
    ids=["eagain", "econnreset", "mbedtls-alert"],
)
def test_accept_retryable_errors(fake_pool, error):
    server = Server(fake_pool([error]))
    server.start("127.0.0.1", 80)

    assert server.poll() == NO_REQUEST


def test_accept_other_error_is_raised(fake_pool):
    server = Server(fake_pool([OSError(errno.EMFILE, "too many open files")]))
    server.start("127.0.0.1", 80)

    with pytest.raises(OSError, match="too many open files"):
        server.poll()


def test_accepted_connection_gets_socket_timeout(fake_pool, fake_socket):
    conn = fake_socket()
    server = Server(fake_pool([conn]))
    server.socket_timeout = 3
    server.start("127.0.0.1", 80)

    assert server.poll() == CONNECTION_TIMED_OUT
    assert conn.timeout == 3
    assert conn.closed


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out"), OSError(errno.ETIMEDOUT, "timed out")],
    ids=["TimeoutError", "ETIMEDOUT"],
)
def test_receive_timeouts(fake_pool, fake_socket, error):
    no_data = fake_socket([error])
    partial_body = fake_socket(
        [b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\n\r\n", b"abc", error]
    )
    server = Server(fake_pool([no_data, partial_body]))

    @server.route("/echo", POST)
    def echo(request):
        return Response(request, request.body)

    server.start("127.0.0.1", 80)

    assert server.poll() == CONNECTION_TIMED_OUT
    assert no_data.closed

    assert server.poll() == REQUEST_HANDLED_RESPONSE_SENT
    assert partial_body.sent.endswith(b"\r\n\r\nabc")


def test_receive_connection_reset(fake_pool, fake_socket):
    conn = fake_socket([ConnectionResetError(errno.ECONNRESET, "reset")])
    server = Server(fake_pool([conn]))
    server.start("127.0.0.1", 80)

    assert server.poll() == NO_REQUEST
    assert conn.closed


def test_receive_other_error_is_raised_and_connection_closed(fake_pool, fake_socket):
    conn = fake_socket([OSError(errno.EBADF, "bad file descriptor")])
    server = Server(fake_pool([conn]))
    server.start("127.0.0.1", 80)

    with pytest.raises(OSError, match="bad file descriptor"):
        server.poll()
    assert conn.closed


def test_body_receive_error_is_raised_and_connection_closed(fake_pool, fake_socket):
    conn = fake_socket(
        [
            b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\n\r\n",
            b"abc",
            OSError(errno.EBADF, "bad file descriptor"),
        ]
    )
    server = Server(fake_pool([conn]))
    server.start("127.0.0.1", 80)

    with pytest.raises(OSError, match="bad file descriptor"):
        server.poll()
    assert conn.closed


# HTTPS


def https_client(port, raw, results):
    """Thread target: send ``raw`` over TLS and store the reply (or exception) in ``results``."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname="localhost") as tls:
                tls.sendall(raw)
                results.append(tls.makefile("rb").read())
    except Exception as error:
        results.append(error)


def test_https(make_server, port_of, parse_response, tls_cert, capsys):
    # Based on examples/httpserver_https.py
    certfile, keyfile = tls_cert
    server = make_server(https=True, certfile=certfile, keyfile=keyfile, debug=True)

    @server.route("/")
    def base(request):
        return Response(request, "Hello from the CircuitPython HTTPS Server!")

    results = []
    thread = threading.Thread(target=https_client, args=(port_of(server), get("/"), results))
    thread.start()
    result = poll_until_request(server)
    thread.join()

    assert result == REQUEST_HANDLED_RESPONSE_SENT
    assert parse_response(results[0]).body == b"Hello from the CircuitPython HTTPS Server!"
    assert "Started development server on https://" in capsys.readouterr().out


@pytest.mark.xfail(
    strict=True,
    reason="A plain-HTTP client connecting to an HTTPS server makes poll() raise SSLError "
    "instead of dropping the connection.",
)
def test_plain_http_client_to_https_server(make_server, port_of, tls_cert):
    certfile, keyfile = tls_cert
    server = make_server(https=True, certfile=certfile, keyfile=keyfile)

    def plain_client():
        with socket.create_connection(("127.0.0.1", port_of(server)), timeout=5) as sock:
            sock.sendall(get("/"))
            try:
                sock.recv(100)
            except OSError:
                pass

    thread = threading.Thread(target=plain_client)
    thread.start()
    try:
        # The client finishes once the server drops the connection; poll() must not raise.
        deadline = time.monotonic() + 5
        while thread.is_alive():
            assert time.monotonic() < deadline, "client did not finish"
            assert server.poll() in {NO_REQUEST, CONNECTION_TIMED_OUT}
            time.sleep(0.01)
    finally:
        thread.join()


@pytest.mark.parametrize(
    "kwargs", [{}, {"certfile": "cert.pem"}, {"keyfile": "key.pem"}], ids=["none", "cert", "key"]
)
def test_https_requires_cert_and_key(fake_pool, kwargs):
    with pytest.raises(ValueError, match="Both certfile and keyfile must be specified"):
        Server(fake_pool(), https=True, **kwargs)
