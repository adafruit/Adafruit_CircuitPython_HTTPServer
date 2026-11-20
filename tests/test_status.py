# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Tests for adafruit_httpserver.Status, the status constants and the method constants."""

from http import HTTPStatus

import pytest

import adafruit_httpserver
from adafruit_httpserver import NOT_FOUND_404, OK_200, Status

STATUS_CONSTANTS = sorted(
    name
    for name in dir(adafruit_httpserver)
    if isinstance(getattr(adafruit_httpserver, name), Status)
)

METHOD_NAMES = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT"]


def test_str_and_repr():
    status = Status(418, "I'm a teapot")

    assert str(status) == "418 I'm a teapot"
    assert repr(status) == '<Status 418, "I\'m a teapot">'


def test_equality():
    assert Status(200, "OK") == OK_200
    assert Status(200, "Fine") != OK_200
    assert Status(404, "OK") != OK_200
    assert OK_200 != NOT_FOUND_404


@pytest.mark.xfail(
    strict=True,
    reason="Status.__eq__ assumes the other object is a Status and raises AttributeError",
)
def test_equality_with_other_types():
    assert OK_200 != 200
    assert OK_200 != None  # noqa: E711 -- exercising __eq__ with None is the point.


def test_status_constants_found():
    # Make sure the scan for STATUS_CONSTANTS found them. Otherwise the parametrized test
    # below would silently run no cases.
    assert "OK_200" in STATUS_CONSTANTS
    assert len(STATUS_CONSTANTS) >= 19


@pytest.mark.parametrize("name", STATUS_CONSTANTS)
def test_status_constant_matches_http_standard(name):
    status = getattr(adafruit_httpserver, name)

    assert name.endswith(f"_{status.code}")
    assert status.text == HTTPStatus(status.code).phrase


@pytest.mark.parametrize("name", METHOD_NAMES)
def test_method_constants(name):
    assert getattr(adafruit_httpserver, name) == name
