# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Tests for Basic, Token and Bearer authentication helpers.

Server-wide ``Server.require_authentication()`` is tested end to end in test_server.py.
"""

import base64

import pytest

from adafruit_httpserver import (
    AuthenticationError,
    Basic,
    Bearer,
    Token,
    check_authentication,
    require_authentication,
)

# Same credentials as examples/httpserver_authentication_handlers.py
AUTHS = [
    Basic("user", "password"),
    Token("2db53340-4f9c-4f70-9037-d25bee77eca6"),
    Bearer("642ec696-2a79-4d60-be3a-7c9a3164d766"),
]


def request_with_authorization(make_request, value):
    if value is None:
        return make_request(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    return make_request(
        f"GET / HTTP/1.1\r\nHost: localhost\r\nAuthorization: {value}\r\n\r\n".encode()
    )


def test_basic_str():
    expected = base64.b64encode(b"user:password").decode()

    assert str(Basic("user", "password")) == f"Basic {expected}"


def test_basic_str_non_ascii_and_colon_in_password():
    expected = base64.b64encode("user:pä:ss".encode()).decode()

    assert str(Basic("user", "pä:ss")) == f"Basic {expected}"


def test_basic_str_long_credentials_not_wrapped():
    auth = str(Basic("u" * 100, "p" * 100))

    assert "\n" not in auth
    assert auth == "Basic " + base64.b64encode(b"u" * 100 + b":" + b"p" * 100).decode()


def test_token_and_bearer_str():
    assert str(Token("abc")) == "Token abc"
    assert str(Bearer("abc")) == "Bearer abc"
    assert isinstance(Bearer("abc"), Token)


@pytest.mark.parametrize("auth", AUTHS, ids=["basic", "token", "bearer"])
def test_check_authentication_accepts_each(make_request, auth):
    request = request_with_authorization(make_request, str(auth))

    assert check_authentication(request, AUTHS) is True
    require_authentication(request, AUTHS)  # Does not raise.


@pytest.mark.parametrize(
    "value",
    [
        None,
        "Basic " + base64.b64encode(b"user:wrong").decode(),
        "Token wrong",
        # Right token, wrong scheme.
        "Bearer 2db53340-4f9c-4f70-9037-d25bee77eca6",
    ],
    ids=["missing", "wrong-password", "wrong-token", "wrong-scheme"],
)
def test_check_authentication_rejects(make_request, value):
    request = request_with_authorization(make_request, value)

    assert check_authentication(request, AUTHS) is False
    with pytest.raises(AuthenticationError):
        require_authentication(request, AUTHS)


def test_check_authentication_with_no_auths(make_request):
    request = request_with_authorization(make_request, str(AUTHS[0]))

    assert check_authentication(request, []) is False


@pytest.mark.xfail(
    strict=True,
    reason="The scheme is compared case-sensitively. RFC 9110 section 11.1 says it is "
    "case-insensitive.",
)
def test_scheme_is_case_insensitive(make_request):
    credentials = base64.b64encode(b"user:password").decode()
    request = request_with_authorization(make_request, f"basic {credentials}")

    assert check_authentication(request, AUTHS) is True
