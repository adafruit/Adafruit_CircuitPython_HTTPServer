# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Tests for adafruit_httpserver.Headers."""

import pytest

from adafruit_httpserver import Headers


def test_parse_from_string():
    headers = Headers("Content-Type: text/html\r\nContent-Length: 1024\r\n")

    assert len(headers) == 2
    assert headers["Content-Type"] == "text/html"
    assert headers["Content-Length"] == "1024"


def test_parse_from_dict():
    headers = Headers({"Content-Type": "text/html", "Content-Length": "1024"})

    assert len(headers) == 2
    assert headers["content-type"] == "text/html"


@pytest.mark.parametrize("source", [None, {}, "", "\r\n"])
def test_empty(source):
    headers = Headers(source)

    assert len(headers) == 0
    assert headers.fields == []


def test_value_may_contain_colon_space():
    headers = Headers("Location: http://example.com/a: b\r\n")

    assert headers["Location"] == "http://example.com/a: b"


@pytest.mark.xfail(
    strict=True,
    reason="Headers splits only on ': '. RFC 9112 section 5 allows no space after the colon.",
)
def test_parse_without_space_after_colon():
    headers = Headers("X-Foo:bar\r\n")

    assert headers["X-Foo"] == "bar"


def test_names_are_case_insensitive():
    headers = Headers({"Content-Type": "text/html"})

    assert headers["CONTENT-TYPE"] == "text/html"
    assert headers.get("content-TYPE") == "text/html"
    assert "content-type" in headers
    assert "CONTENT-TYPE" in headers
    assert headers.get_list("Content-type") == ["text/html"]


def test_names_are_stored_lowercase():
    headers = Headers({"Content-Type": "text/html"})

    assert headers.fields == ["content-type"]
    assert headers.keys() == ["content-type"]


def test_missing_name():
    headers = Headers()

    with pytest.raises(KeyError):
        headers["User-Agent"]
    assert headers.get("User-Agent") is None
    assert headers.get("User-Agent", "default") == "default"
    assert headers.get_list("User-Agent") == []
    assert "User-Agent" not in headers


def test_add_keeps_multiple_values():
    headers = Headers()
    headers.add("Set-Cookie", "a=1")
    headers.add("set-cookie", "b=2")

    assert len(headers) == 1
    assert headers["Set-Cookie"] == "a=1"
    assert headers.get_list("Set-Cookie") == ["a=1", "b=2"]
    assert headers.items() == [("set-cookie", "a=1"), ("set-cookie", "b=2")]
    assert headers.values() == ["a=1", "b=2"]


def test_parse_repeated_header_from_string():
    headers = Headers("Set-Cookie: a=1\r\nSet-Cookie: b=2\r\n")

    assert headers.get_list("set-cookie") == ["a=1", "b=2"]


def test_set_and_setitem_replace_all_values():
    headers = Headers("Set-Cookie: a=1\r\nSet-Cookie: b=2\r\n")

    headers.set("SET-COOKIE", "c=3")
    assert headers.get_list("Set-Cookie") == ["c=3"]

    headers["Set-Cookie"] = "d=4"
    assert headers.get_list("Set-Cookie") == ["d=4"]


def test_setdefault_does_not_overwrite():
    headers = Headers({"Access-Control-Allow-Origin": "example.com"})

    headers.setdefault("access-control-allow-origin", "*")
    headers.setdefault("X-New", "value")

    assert headers["Access-Control-Allow-Origin"] == "example.com"
    assert headers["x-new"] == "value"


def test_update_replaces_values():
    headers = Headers("Set-Cookie: a=1\r\nSet-Cookie: b=2\r\nX-Keep: yes\r\n")

    headers.update({"set-cookie": "c=3", "X-New": "new"})

    assert headers.get_list("Set-Cookie") == ["c=3"]
    assert headers["X-Keep"] == "yes"
    assert headers["X-New"] == "new"


def test_delitem():
    headers = Headers({"Content-Type": "text/html"})

    del headers["CONTENT-TYPE"]

    assert "Content-Type" not in headers
    with pytest.raises(KeyError):
        del headers["Content-Type"]


def test_copy_is_independent_and_keeps_multiple_values():
    headers = Headers("Set-Cookie: a=1\r\nSet-Cookie: b=2\r\n")

    copied = headers.copy()
    copied.add("Set-Cookie", "c=3")
    copied["X-Other"] = "x"

    assert isinstance(copied, Headers)
    assert copied.get_list("Set-Cookie") == ["a=1", "b=2", "c=3"]
    assert headers.get_list("Set-Cookie") == ["a=1", "b=2"]
    assert "X-Other" not in headers


def test_iteration_and_repr():
    headers = Headers({"A": "1", "B": "2"})

    assert list(headers) == ["a", "b"]
    assert repr(headers) == "<Headers {'a': ['1'], 'b': ['2']}>"


def test_get_directive():
    headers = Headers({"Content-Type": "text/html; charset=utf-8", "X-Quoted": '"quoted"'})

    assert headers.get_directive("Content-Type") == "text/html"
    assert headers.get_directive("X-Quoted") == "quoted"
    assert headers.get_directive("Missing") is None
    assert headers.get_directive("Missing", "default") == "default"


def test_get_parameter():
    headers = Headers(
        {
            "Content-Disposition": 'form-data; name="field"; filename="file.txt"',
            "Content-Type": "text/html; charset=utf-8",
        }
    )

    assert headers.get_parameter("Content-Disposition", "name") == "field"
    assert headers.get_parameter("Content-Disposition", "filename") == "file.txt"
    assert headers.get_parameter("content-type", "charset") == "utf-8"


def test_get_parameter_missing():
    headers = Headers({"Content-Type": "text/html"})

    assert headers.get_parameter("Content-Type", "charset") is None
    assert headers.get_parameter("Content-Type", "charset", "utf-8") == "utf-8"
    assert headers.get_parameter("Missing", "charset") is None
    assert headers.get_parameter("Missing", "charset", "default") == "default"


@pytest.mark.xfail(
    strict=True,
    reason="get_parameter() matches parameter names by prefix, so 'charset' matches 'charsetx'",
)
def test_get_parameter_matches_whole_name():
    headers = Headers({"Content-Type": "text/plain; charsetx=wrong; charset=utf-8"})

    assert headers.get_parameter("Content-Type", "charset") == "utf-8"


@pytest.mark.xfail(
    strict=True,
    reason="get_parameter() cuts a value off at its first '='. RFC 2046 allows '=' in a "
    "multipart boundary.",
)
def test_get_parameter_value_containing_equals():
    headers = Headers({"Content-Type": 'multipart/form-data; boundary="----=_Part_0"'})

    assert headers.get_parameter("Content-Type", "boundary") == "----=_Part_0"
