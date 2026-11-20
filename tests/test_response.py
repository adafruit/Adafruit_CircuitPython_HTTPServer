# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Tests for Response, FileResponse, ChunkedResponse, JSONResponse, Redirect and SSEResponse.

Responses are sent to a ``FakeSocket`` by calling ``_send()``, which is what
``Server.poll()`` does. Websocket is tested in test_websocket.py.
"""

import errno
import json

import pytest

from adafruit_httpserver import (
    FOUND_302,
    MOVED_PERMANENTLY_301,
    NOT_FOUND_404,
    PERMANENT_REDIRECT_308,
    TEMPORARY_REDIRECT_307,
    BackslashInPathError,
    ChunkedResponse,
    FileNotExistsError,
    FileResponse,
    Headers,
    JSONResponse,
    MIMETypes,
    ParentDirectoryReferenceError,
    Redirect,
    Response,
    Server,
    SSEResponse,
)

GET_ROOT = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"


@pytest.fixture
def new_request(make_request, fake_socket):
    """Factory returning ``(request, conn)``. Keyword arguments go to ``FakeSocket``."""

    def factory(raw=GET_ROOT, *, server=None, **socket_kwargs):
        conn = fake_socket(**socket_kwargs)
        return make_request(raw, conn=conn, server=server), conn

    return factory


@pytest.fixture
def send(parse_response):
    """``send(response)`` calls ``response._send()`` and returns the parsed reply."""

    def sender(response):
        response._send()
        return parse_response(bytes(response._request.connection.sent))

    return sender


@pytest.fixture
def www(tmp_path):
    """A root_path directory with a few files."""
    (tmp_path / "index.html").write_text("<h1>Home</h1>")
    (tmp_path / "style.css").write_text("body {}")
    (tmp_path / "data.bin").write_bytes(bytes(range(256)) * 10)
    (tmp_path / "my file.txt").write_text("spaces")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "index.html").write_text("<h1>Sub</h1>")
    (tmp_path / "a..b.txt").write_text("dots")
    return tmp_path


def decode_chunked(body: bytes):
    """Return the chunks in a chunked body. Check that it ends with the zero-length final chunk."""
    chunks = []
    while True:
        size_line, body = body.split(b"\r\n", 1)
        size = int(size_line, 16)
        chunk, trailer, body = body[:size], body[size : size + 2], body[size + 2 :]
        assert trailer == b"\r\n"
        if size == 0:
            assert body == b""
            return chunks
        chunks.append(chunk)


# Response


def test_response_defaults(new_request, send):
    request, conn = new_request()
    reply = send(Response(request, "Hello from the CircuitPython HTTP Server!"))

    assert reply.status_line == "HTTP/1.1 200 OK"
    assert reply.header("Content-Type") == "text/plain"
    assert reply.header("Content-Length") == "41"
    assert reply.header("Connection") == "close"
    assert reply.body == b"Hello from the CircuitPython HTTP Server!"
    assert conn.closed


def test_response_empty_body(new_request, send):
    request, _ = new_request()
    reply = send(Response(request))

    assert reply.header("Content-Length") == "0"
    assert reply.body == b""


def test_response_utf8_content_length(new_request, send):
    request, _ = new_request()
    reply = send(Response(request, "héllo ✓"))

    assert reply.body == "héllo ✓".encode()
    assert reply.header("Content-Length") == str(len("héllo ✓".encode()))


def test_response_bytes_body(new_request, send):
    request, _ = new_request()
    reply = send(Response(request, b"\x00\x01\xff", content_type="application/octet-stream"))

    assert reply.body == b"\x00\x01\xff"
    assert reply.header("Content-Type") == "application/octet-stream"


def test_response_status_object_and_tuple(new_request, send):
    request, _ = new_request()
    assert send(Response(request, status=NOT_FOUND_404)).status_line == "HTTP/1.1 404 Not Found"

    request, _ = new_request()
    reply = send(Response(request, status=(418, "I'm a teapot")))
    assert reply.status_line == "HTTP/1.1 418 I'm a teapot"


def test_response_default_content_type_follows_mime_types_config(new_request, send):
    MIMETypes.configure(default_to="application/octet-stream")
    request, _ = new_request()

    assert send(Response(request, "x")).header("Content-Type") == "application/octet-stream"


def test_response_headers_dict_and_headers_object(new_request, send):
    request, _ = new_request()
    reply = send(Response(request, "x", headers={"X-Custom": "1"}))
    assert reply.header("X-Custom") == "1"

    headers = Headers({"X-Custom": "2"})
    request, _ = new_request()
    response = Response(request, "x", headers=headers)
    headers["X-Custom"] = "changed after"
    assert send(response).header("X-Custom") == "2"


def test_response_explicit_header_overrides_content_type_argument(new_request, send):
    request, _ = new_request()
    response = Response(
        request, "x", content_type="text/html", headers={"Content-Type": "text/csv"}
    )

    assert send(response).header("Content-Type") == "text/csv"


def test_response_cookies_and_set_cookie_headers(new_request, send):
    # Based on examples/httpserver_cookies.py
    headers = Headers()
    headers.add("Set-Cookie", "cookie1=value1")
    headers.add("Set-Cookie", "cookie2=value2")
    request, _ = new_request()
    reply = send(Response(request, "x", headers=headers, cookies={"theme": "dark"}))

    assert sorted(reply.headers["set-cookie"]) == [
        "cookie1=value1",
        "cookie2=value2",
        "theme=dark",
    ]


def test_response_size_counts_bytes_sent(new_request, send):
    request, conn = new_request()
    response = Response(request, "Hello")
    send(response)

    assert response._size == len(conn.sent)


# Sending: partial sends and socket errors


def test_partial_sends_are_completed(new_request, send):
    request, conn = new_request(max_send=3)
    reply = send(Response(request, "Hello, world"))

    assert reply.body == b"Hello, world"
    assert conn.send_calls > 10


def test_eagain_on_send_is_retried(new_request, send):
    request, conn = new_request(send_errors=[OSError(errno.EAGAIN, "try again"), None])
    reply = send(Response(request, "Hello"))

    assert reply.body == b"Hello"
    assert conn.closed


def test_connection_reset_on_send_is_ignored(new_request):
    request, conn = new_request(send_errors=[ConnectionResetError(errno.ECONNRESET, "reset")])

    Response(request, "Hello")._send()  # Does not raise.

    assert conn.closed


def test_other_send_error_is_raised(new_request):
    request, _ = new_request(send_errors=[BrokenPipeError(errno.EPIPE, "broken pipe")])

    with pytest.raises(BrokenPipeError):
        Response(request, "Hello")._send()


def test_error_closing_connection_is_ignored(new_request):
    request, conn = new_request()

    def failing_close():
        raise OSError(errno.EBADF, "bad file descriptor")

    conn.close = failing_close

    Response(request, "Hello")._send()  # Does not raise.


# FileResponse


def file_server(fake_pool, root):
    return Server(fake_pool(), str(root))


def test_file_response_uses_server_root_path(new_request, send, fake_pool, www):
    request, conn = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "style.css"))

    assert reply.status == 200
    assert reply.header("Content-Type") == "text/css"
    assert reply.header("Content-Length") == "7"
    assert reply.body == b"body {}"
    assert conn.closed


def test_file_response_explicit_root_path(new_request, send, fake_pool, www, tmp_path_factory):
    # Based on examples/httpserver_handler_serves_file.py
    other_root = tmp_path_factory.mktemp("other")
    (other_root / "home.html").write_text("<p>other</p>")
    request, _ = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "home.html", str(other_root)))

    assert reply.header("Content-Type") == "text/html"
    assert reply.body == b"<p>other</p>"


def test_file_response_root_path_without_server_root(new_request, send, www):
    request, _ = new_request()
    reply = send(FileResponse(request, "/style.css", str(www) + "/"))

    assert reply.body == b"body {}"


def test_file_response_default_filename_and_trailing_slash(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www))
    assert send(FileResponse(request)).body == b"<h1>Home</h1>"

    request, _ = new_request(server=file_server(fake_pool, www))
    assert send(FileResponse(request, "/sub/")).body == b"<h1>Sub</h1>"


def test_file_response_binary_with_small_buffer(new_request, send, fake_pool, www):
    request, conn = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "data.bin", buffer_size=1000))

    assert reply.body == bytes(range(256)) * 10
    assert reply.header("Content-Length") == "2560"
    assert reply.header("Content-Type") == "application/octet-stream"
    assert conn.send_calls == 1 + 3  # Headers, then 1000 + 1000 + 560 bytes.


def test_file_response_head_only(new_request, send, fake_pool, www):
    request, conn = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "style.css", head_only=True))

    assert reply.header("Content-Length") == "7"
    assert reply.body == b""
    assert conn.closed


def test_file_response_content_type_argument(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "style.css", content_type="text/x-custom"))

    assert reply.header("Content-Type") == "text/x-custom"


def test_file_response_as_attachment(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "/sub/index.html", as_attachment=True))
    assert reply.header("Content-Disposition") == "attachment; filename=index.html"

    request, _ = new_request(server=file_server(fake_pool, www))
    reply = send(
        FileResponse(request, "style.css", as_attachment=True, download_filename="theme.css")
    )
    assert reply.header("Content-Disposition") == "attachment; filename=theme.css"


@pytest.mark.xfail(
    strict=True,
    reason="The Content-Disposition filename is not quoted. RFC 6266 section 4.1 requires a "
    "quoted string for a name with spaces.",
)
def test_file_response_attachment_filename_with_space(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www))
    reply = send(FileResponse(request, "my file.txt", as_attachment=True))

    assert reply.header("Content-Disposition") == 'attachment; filename="my file.txt"'


def test_file_response_without_any_root_path_raises(new_request):
    request, _ = new_request()

    with pytest.raises(ValueError, match="root_path must be provided"):
        FileResponse(request, "index.html")


@pytest.mark.parametrize(
    ("filename", "error"),
    [
        ("/../secret.txt", ParentDirectoryReferenceError),
        ("/sub/../../secret.txt", ParentDirectoryReferenceError),
        ("..", ParentDirectoryReferenceError),
        ("/sub\\index.html", BackslashInPathError),
    ],
)
def test_file_response_rejects_unsafe_paths(new_request, fake_pool, www, filename, error):
    request, _ = new_request(server=file_server(fake_pool, www))

    with pytest.raises(error, match="path: "):
        FileResponse(request, filename)


def test_file_response_allows_double_dots_inside_a_name(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www))

    assert send(FileResponse(request, "a..b.txt")).body == b"dots"


def test_file_response_percent_encoded_dots_are_not_decoded(new_request, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www / "sub"))

    with pytest.raises(FileNotExistsError):
        FileResponse(request, "/%2e%2e/index.html")


def test_file_response_safe_false_skips_path_check(new_request, send, fake_pool, www):
    request, _ = new_request(server=file_server(fake_pool, www / "sub"))

    assert send(FileResponse(request, "/../style.css", safe=False)).body == b"body {}"


@pytest.mark.parametrize("filename", ["missing.html", "/sub", "/sub/missing/"])
def test_file_response_not_a_regular_file(new_request, fake_pool, www, filename):
    request, _ = new_request(server=file_server(fake_pool, www))

    with pytest.raises(FileNotExistsError, match="File does not exist: "):
        FileResponse(request, filename)


# ChunkedResponse


def test_chunked_response(new_request, send):
    # From examples/httpserver_chunked.py
    def body():
        yield "Adaf"
        yield b"ruit"
        yield " Indus"
        yield b"tr"
        yield "ies"

    request, conn = new_request()
    reply = send(ChunkedResponse(request, body))

    assert reply.header("Transfer-Encoding") == "chunked"
    assert reply.header("Content-Length") is None
    assert decode_chunked(reply.body) == [b"Adaf", b"ruit", b" Indus", b"tr", b"ies"]
    assert conn.closed


def test_chunked_response_skips_empty_chunks_and_counts_utf8_bytes(new_request, send):
    def body():
        yield ""
        yield "✓" * 10
        yield b""

    request, _ = new_request()
    reply = send(ChunkedResponse(request, body, content_type="text/html"))

    assert reply.header("Content-Type") == "text/html"
    assert reply.body.startswith(b"1e\r\n")  # 30 bytes of UTF-8.
    assert decode_chunked(reply.body) == ["✓".encode() * 10]


def test_chunked_response_no_chunks(new_request, send):
    request, _ = new_request()
    reply = send(ChunkedResponse(request, lambda: iter(())))

    assert reply.body == b"0\r\n\r\n"


# JSONResponse


@pytest.mark.parametrize(
    "data", [{"message": "Object added", "object": {"id": 2}}, [{"id": 1, "name": "Object 1"}]]
)
def test_json_response(new_request, send, data):
    request, conn = new_request()
    reply = send(JSONResponse(request, data))

    assert reply.header("Content-Type") == "application/json"
    assert json.loads(reply.body) == data
    assert reply.header("Content-Length") == str(len(reply.body))
    assert conn.closed


def test_json_response_status_and_headers(new_request, send):
    request, _ = new_request()
    reply = send(JSONResponse(request, {}, status=NOT_FOUND_404, headers={"X-A": "1"}))

    assert reply.status == 404
    assert reply.header("X-A") == "1"


def test_json_response_unserializable_data_raises(new_request):
    request, _ = new_request()

    with pytest.raises(TypeError):
        JSONResponse(request, {"x": object()})._send()


# Redirect


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({}, FOUND_302),
        ({"permanent": True}, MOVED_PERMANENTLY_301),
        ({"preserve_method": True}, TEMPORARY_REDIRECT_307),
        ({"permanent": True, "preserve_method": True}, PERMANENT_REDIRECT_308),
        ({"status": MOVED_PERMANENTLY_301}, MOVED_PERMANENTLY_301),
    ],
)
def test_redirect(new_request, send, kwargs, status):
    # Based on examples/httpserver_redirects.py
    request, conn = new_request()
    reply = send(Redirect(request, "https://circuitpython.org/blinka", **kwargs))

    assert reply.status == status.code
    assert reply.reason == status.text
    assert reply.header("Location") == "https://circuitpython.org/blinka"
    assert reply.body == b""
    assert conn.closed


@pytest.mark.parametrize("flag", ["permanent", "preserve_method"])
def test_redirect_status_with_flag_raises(new_request, flag):
    request, _ = new_request()

    with pytest.raises(ValueError, match="Cannot specify both status and"):
        Redirect(request, "/x", status=FOUND_302, **{flag: True})


def test_redirect_cookies(new_request, send):
    request, _ = new_request()
    reply = send(Redirect(request, "/login", cookies={"session": "abc"}))

    assert reply.header("Set-Cookie") == "session=abc"


# SSEResponse


def test_sse_response_headers_keep_connection_open(new_request, send):
    request, conn = new_request()
    reply = send(SSEResponse(request))

    assert reply.status == 200
    assert reply.header("Content-Type") == "text/event-stream"
    assert reply.header("Cache-Control") == "no-cache"
    assert reply.header("Connection") == "keep-alive"
    assert reply.header("Content-Length") is None
    assert not conn.closed


def test_sse_send_event(new_request):
    request, conn = new_request()
    sse = SSEResponse(request)
    sse._send()
    del conn.sent[:]

    sse.send_event("23.5")
    sse.send_event("Message", event="name", id=1, retry=5000, custom_fields={"x": "y"})

    assert bytes(conn.sent) == (
        b"data: 23.5\n\ndata: Message\nevent: name\nid: 1\nretry: 5000\nx: y\n\n"
    )


def dispatched_sse_events(stream: str):
    """
    ``(type, data)`` for each event a browser would dispatch from ``stream``.

    Follows the event stream interpretation rules in HTML Standard section 9.2.6, including its
    "dispatch the event" steps:
    https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation

    Retry and id fields are ignored.
    """
    events = []
    data, event_type = "", ""
    lines = stream.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # The last item is whatever follows the final line ending. It is an incomplete line,
    # which the spec discards at end of stream.
    for line in lines[:-1]:
        if line == "":
            # "Dispatch the event" step 2: an empty data buffer means nothing is dispatched.
            if data:
                events.append((event_type or "message", data.removesuffix("\n")))
            data, event_type = "", ""
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "data":
            data += value + "\n"
        elif field == "event":
            event_type = value
    # At end of stream, a pending event without its final blank line is discarded.
    return events


@pytest.mark.skip(
    reason="Not run: probable bug, intent unclear. close() writes 'event: close' with no data "
    "field and no blank line after it. A browser's EventSource delivers only events that have "
    "data and end with a blank line, so the client never sees it. The client sees only a dropped "
    "connection, and EventSource then reconnects. Neither the close() docstring nor "
    "examples/httpserver_sse.py mentions a close event, so it may not be meant for clients."
)
def test_sse_close_event_is_dispatched(new_request):
    request, conn = new_request()
    sse = SSEResponse(request)
    sse._send()
    del conn.sent[:]

    sse.send_event("last reading")
    sse.close()

    assert dispatched_sse_events(conn.sent.decode()) == [
        ("message", "last reading"),
        ("close", ""),
    ]


def test_sse_close(new_request):
    request, conn = new_request()
    sse = SSEResponse(request)
    sse._send()
    del conn.sent[:]

    sse.close()

    assert bytes(conn.sent).startswith(b"event: close\n")
    assert conn.closed


@pytest.mark.xfail(
    strict=True,
    reason="send_event() puts multi-line data in one 'data:' field. The SSE format needs a "
    "'data:' line for each line of data. Otherwise the later lines are lost.",
)
def test_sse_multiline_data(new_request):
    request, conn = new_request()
    sse = SSEResponse(request)
    sse.send_event("line 1\nline 2")

    assert bytes(conn.sent) == b"data: line 1\ndata: line 2\n\n"


@pytest.mark.xfail(strict=True, reason="send_event() omits id=0 and retry=0 because they are falsy")
def test_sse_zero_id_and_retry(new_request):
    request, conn = new_request()
    sse = SSEResponse(request)
    sse.send_event("x", id=0, retry=0)

    assert bytes(conn.sent) == b"data: x\nid: 0\nretry: 0\n\n"
