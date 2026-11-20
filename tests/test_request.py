# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Tests for adafruit_httpserver.Request, QueryParams, FormData and File."""

import json

import pytest

from adafruit_httpserver import DELETE, GET, PATCH, POST, PUT, FormData, QueryParams, Server

XSS_WARNING = "WARNING: Setting safe to False makes XSS vulnerabilities possible"


def raw_request(method="GET", target="/", headers=None, body=b""):
    """Build raw request bytes, adding Host and (for a body) Content-Length."""
    lines = [f"{method} {target} HTTP/1.1", "Host: localhost"]
    lines += [f"{name}: {value}" for name, value in (headers or {}).items()]
    if body:
        lines.append(f"Content-Length: {len(body)}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


def multipart_body(boundary, parts):
    """
    Build a multipart/form-data body.

    ``parts`` is a list of ``(name, filename_or_None, content_type_or_None, content_bytes)``.
    """
    body = b""
    for name, filename, content_type, content in parts:
        disposition = f'form-data; name="{name}"'
        if filename is not None:
            disposition += f'; filename="{filename}"'
        body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\n".encode()
        if content_type is not None:
            body += f"Content-Type: {content_type}\r\n".encode()
        body += b"\r\n" + content + b"\r\n"
    return body + f"--{boundary}--\r\n".encode()


def form_request(make_request, content_type, body, *, server=None):
    return make_request(
        raw_request(POST, "/form", {"Content-Type": content_type}, body), server=server
    )


# Request line, headers and body


def test_parse_request(make_request, fake_socket):
    conn = fake_socket()
    request = make_request(
        b"GET /path/to?x=1 HTTP/1.1\r\nHost: localhost\r\nUser-Agent: test\r\n\r\n", conn=conn
    )

    assert request.method == GET
    assert request.path == "/path/to"
    assert request.query_params["x"] == "1"
    assert request.http_version == "HTTP/1.1"
    assert request.headers["host"] == "localhost"
    assert request.headers["User-Agent"] == "test"
    assert request.body == b""
    assert request.connection is conn
    assert request.client_address == ("127.0.0.1", 54321)


def test_body(make_request):
    request = make_request(raw_request(POST, "/", body=b"payload\r\n\r\nwith blank line"))

    assert request.body == b"payload\r\n\r\nwith blank line"


def test_body_setter_replaces_body(make_request):
    request = make_request(raw_request(POST, "/", body=b"old"))

    request.body = b"new body"

    assert request.body == b"new body"
    assert request.raw_request.endswith(b"\r\n\r\nnew body")
    assert request.headers["Host"] == "localhost"


def test_repr(make_request):
    assert repr(make_request(raw_request(GET, "/p"))) == '<Request "GET /p">'
    assert repr(make_request(raw_request(GET, "/p?a=1&b=2"))) == '<Request "GET /p?a=1&b=2">'


def test_raw_request_none_raises(fake_pool, fake_socket):
    from adafruit_httpserver import Request

    with pytest.raises(ValueError, match="raw_request cannot be None"):
        Request(Server(fake_pool()), fake_socket(), ("127.0.0.1", 1), None)


@pytest.mark.parametrize(
    "raw",
    [b"", b"garbage", b"GET /\r\nHost: localhost\r\n\r\n", b"\xff\xfe\r\nHost: x\r\n\r\n"],
    ids=["empty", "garbage", "missing-version", "not-utf8"],
)
def test_unparseable_request_raises(make_request, raw):
    with pytest.raises(ValueError, match="Unparseable raw_request"):
        make_request(raw)


@pytest.mark.xfail(
    strict=True,
    reason="A request with no header lines raises ValueError. HTTP/1.0 does not require any.",
)
def test_request_without_headers(make_request):
    request = make_request(b"GET / HTTP/1.0\r\n\r\n")

    assert request.method == GET
    assert len(request.headers) == 0


@pytest.mark.xfail(
    strict=True,
    reason="A request whose last header has an empty value raises ValueError. The parser strips "
    "the header block, which removes the space after the colon, so the line no longer splits on "
    "': '.",
)
def test_empty_value_on_last_header(make_request):
    request = make_request(b"GET / HTTP/1.1\r\nHost: localhost\r\nAuthorization: \r\n\r\n")

    assert request.headers["Authorization"] == ""


# Query parameters


def test_query_params(make_request):
    request = make_request(raw_request(GET, "/?foo=bar&baz=qux&baz=quux&flag&eq=a=b"))
    params = request.query_params

    assert isinstance(params, QueryParams)
    assert params["foo"] == "bar"
    assert params.get("baz") == "qux"
    assert params.get_list("baz") == ["qux", "quux"]
    assert params.get("flag") == ""
    assert params.get("eq") == "a=b"
    assert params.fields == ["foo", "baz", "flag", "eq"]
    assert "flag" in params
    assert "missing" not in params
    assert params.get("missing") is None
    assert params.get("missing", "default") == "default"


@pytest.mark.parametrize("target", ["/", "/?", "/?&&"])
def test_no_query_params(make_request, target):
    request = make_request(raw_request(GET, target))

    assert request.path == "/"
    assert len(request.query_params) == 0


def test_query_params_str():
    assert str(QueryParams("a=1&b=2&a=3")) == "a=1&a=3&b=2"
    assert str(QueryParams("flag")) == "flag="


@pytest.mark.xfail(strict=True, reason="Query parameter names and values are not percent-decoded")
def test_query_params_are_percent_decoded(make_request):
    request = make_request(raw_request(GET, "/?q=hello%20world%21&caf%C3%A9=1"))

    assert request.query_params.get("q") == "hello world!"
    assert request.query_params.get("café") == "1"


def test_query_params_are_html_escaped_by_default():
    params = QueryParams("x=<script>alert('1')</script>&x=\"quoted\"")

    assert params.get("x") == "&lt;script&gt;alert(&apos;1&apos;)&lt;/script&gt;"
    # Indexing with [] returns the raw value. Only get() escapes.
    assert params["x"] == "<script>alert('1')</script>"
    assert params.get_list("x")[1] == "&quot;quoted&quot;"
    assert params.get("missing", "<b>") == "&lt;b&gt;"
    assert params.get("missing") is None


def test_query_params_safe_false_returns_raw_and_warns(capsys):
    params = QueryParams("x=<b>")

    assert params.get("x", safe=False) == "<b>"
    assert params.get_list("x", safe=False) == ["<b>"]
    assert capsys.readouterr().out.count(XSS_WARNING) == 2


# Cookies


def test_cookies(make_request):
    # Example from the Request.cookies docstring.
    request = make_request(raw_request(GET, "/", {"Cookie": 'foo=bar; baz="qux"; foo=quux'}))

    assert request.cookies == {"foo": "quux", "baz": "qux"}
    assert request.cookies is request.cookies  # Parsed once.


def test_cookie_value_containing_equals(make_request):
    request = make_request(raw_request(GET, "/", {"Cookie": "token=a=b"}))

    assert request.cookies == {"token": "a=b"}


def test_no_cookies(make_request):
    assert make_request(raw_request(GET, "/")).cookies == {}


@pytest.mark.xfail(
    strict=True,
    reason="request.cookies raises ValueError on a cookie without '=', and on a trailing ';'.",
)
@pytest.mark.parametrize("cookie", ["flag", "a=1;"])
def test_lenient_cookie_parsing(make_request, cookie):
    request = make_request(raw_request(GET, "/", {"Cookie": cookie}))

    assert isinstance(request.cookies, dict)


# JSON


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_json(make_request, method):
    # Based on examples/httpserver_methods.py
    request = make_request(raw_request(method, "/api", body=b'{"id": 1, "name": "Object 1"}'))

    assert request.json() == {"id": 1, "name": "Object 1"}


def test_json_not_available_for_get(make_request):
    request = make_request(raw_request(GET, "/api", body=b'{"id": 1}'))

    assert request.json() is None


def test_json_empty_body(make_request):
    assert make_request(raw_request(POST, "/api")).json() is None


def test_json_invalid_body_raises(make_request):
    request = make_request(raw_request(POST, "/api", body=b"{not json"))

    with pytest.raises(json.JSONDecodeError):
        request.json()


# Form data


def test_form_data_none_for_get(make_request):
    assert make_request(raw_request(GET, "/form")).form_data is None


def test_form_data_urlencoded(make_request):
    request = form_request(
        make_request, "application/x-www-form-urlencoded", b"foo=bar&baz=qux&baz=quux&flag"
    )
    form = request.form_data

    assert isinstance(form, FormData)
    assert form.content_type == "application/x-www-form-urlencoded"
    assert form["foo"] == "bar"
    assert form.get_list("baz") == ["qux", "quux"]
    assert form.get("flag") == ""
    assert form.fields == ["foo", "baz", "flag"]
    assert len(form.files) == 0
    assert request.form_data is form  # Parsed once.


def test_form_data_urlencoded_with_charset_parameter(make_request):
    request = form_request(
        make_request, "application/x-www-form-urlencoded; charset=UTF-8", b"something=x"
    )

    assert request.form_data.get("something") == "x"


def test_form_data_urlencoded_empty(make_request):
    request = make_request(
        raw_request(
            POST,
            "/form",
            {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": "0"},
        )
    )

    assert len(request.form_data) == 0


def test_form_data_ignores_bytes_past_content_length(make_request):
    request = make_request(
        b"POST /form HTTP/1.1\r\nContent-Type: application/x-www-form-urlencoded\r\n"
        b"Content-Length: 7\r\n\r\nfoo=barEXTRA"
    )

    assert request.form_data.get("foo") == "bar"


@pytest.mark.xfail(
    strict=True,
    reason="Form values sent as application/x-www-form-urlencoded are not decoded. '+' and %XX "
    "escapes are returned as sent.",
)
def test_form_data_urlencoded_is_decoded(make_request):
    # A browser sends "hello world!" typed into examples/httpserver_form_data.py like this.
    request = form_request(
        make_request, "application/x-www-form-urlencoded", b"something=hello+world%21"
    )

    assert request.form_data.get("something") == "hello world!"


def test_form_data_text_plain(make_request):
    request = form_request(make_request, "text/plain", b"foo=bar\r\nbaz=qux\r\nbaz=a=b\r\n")
    form = request.form_data

    assert form["foo"] == "bar"
    assert form.get_list("baz") == ["qux", "a=b"]


def test_form_data_multipart_fields_and_files(make_request):
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\xff"
    body = multipart_body(
        "XyZ",
        [
            ("something", None, None, "héllo".encode()),
            ("something", None, None, b"second"),
            ("upload", "notes.txt", "text/plain", b"line 1\r\nline 2"),
            ("upload", "image.png", "image/png", png_bytes),
        ],
    )
    request = form_request(make_request, "multipart/form-data; boundary=XyZ", body)
    form = request.form_data

    assert form.get_list("something") == ["héllo", "second"]
    assert "upload" not in form

    text_file, image_file = form.files.get_list("upload")
    assert form.files.get("upload") is text_file
    assert form.files.fields == ["upload"]

    assert text_file.filename == "notes.txt"
    assert text_file.content_type == "text/plain"
    assert text_file.content == "line 1\r\nline 2"
    assert text_file.content_bytes == b"line 1\r\nline 2"
    assert text_file.size == 14
    assert repr(text_file) == "<File filename='notes.txt', content_type='text/plain', size=14>"

    assert image_file.content_type == "image/png"
    assert image_file.content == png_bytes
    assert image_file.content_bytes == png_bytes
    assert image_file.size == len(png_bytes)


def test_form_data_multipart_charset(make_request):
    body = multipart_body(
        "b", [("x", None, "text/plain; charset=latin-1", "café".encode("latin-1"))]
    )
    request = form_request(make_request, "multipart/form-data; boundary=b", body)

    assert request.form_data.get("x") == "café"


@pytest.mark.xfail(
    strict=True, reason="multipart/form-data without a boundary raises AttributeError"
)
def test_form_data_multipart_without_boundary(make_request):
    request = form_request(make_request, "multipart/form-data", b"anything")

    assert len(request.form_data) == 0


@pytest.mark.skip(
    reason="Not run: design question. form_data is parsed only for POST. It is None for PUT and "
    "PATCH even when they carry a form body."
)
@pytest.mark.parametrize("method", [PUT, PATCH])
def test_form_data_for_put_and_patch(make_request, method):
    request = make_request(
        raw_request(
            method, "/form", {"Content-Type": "application/x-www-form-urlencoded"}, b"foo=bar"
        )
    )

    assert request.form_data.get("foo") == "bar"


@pytest.mark.skip(
    reason="Not run: design question. A multipart part with a textual content type other than "
    "text/plain (for example application/json) is returned as bytes. See the TODO in "
    "FormData._parse_multipart_form_data()."
)
def test_form_data_multipart_json_part_is_decoded(make_request):
    body = multipart_body("b", [("settings", None, "application/json", b'{"a": 1}')])
    request = form_request(make_request, "multipart/form-data; boundary=b", body)

    assert request.form_data.get("settings", safe=False) == '{"a": 1}'


@pytest.mark.skip(
    reason="Not run: design question. A text/plain form body without a final CRLF loses its last "
    "field. Browsers always send the final CRLF, because the HTML Standard's text/plain encoding "
    "ends each pair with one. Other clients may not."
)
def test_form_data_text_plain_without_final_crlf(make_request):
    request = form_request(make_request, "text/plain", b"foo=bar\r\nbaz=qux")

    assert request.form_data.get("baz") == "qux"


def test_form_data_values_are_html_escaped_by_default(make_request, capsys):
    request = form_request(make_request, "text/plain", b"x=<b>\r\ny=a&b\r\n")

    assert request.form_data.get("x") == "&lt;b&gt;"
    assert request.form_data.get("y") == "a&amp;b"
    assert request.form_data.get_list("x") == ["&lt;b&gt;"]
    assert request.form_data.get("x", safe=False) == "<b>"
    assert XSS_WARNING in capsys.readouterr().out


def test_form_data_unsupported_content_type(make_request, capsys):
    request = form_request(make_request, "application/json", b'{"a": 1}')

    assert len(request.form_data) == 0
    assert capsys.readouterr().out == ""


def test_form_data_unsupported_content_type_debug_warning(make_request, fake_pool, capsys):
    server = Server(fake_pool(), debug=True)
    request = form_request(make_request, "application/json", b'{"a": 1}', server=server)

    assert len(request.form_data) == 0
    assert "WARNING: Unsupported Content-Type: application/json" in capsys.readouterr().out


def test_form_data_repr(make_request):
    body = multipart_body("b", [("x", None, None, b"1"), ("f", "a.txt", "text/plain", b"hi")])
    request = form_request(make_request, "multipart/form-data; boundary=b", body)

    assert repr(request.form_data) == (
        "<FormData {'x': ['1']}, files={'f': "
        "[<File filename='a.txt', content_type='text/plain', size=2>]}>"
    )
