# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Tests for adafruit_httpserver.MIMETypes.

MIMETypes keeps its configuration in class attributes. The autouse ``_restore_mime_types``
fixture in conftest.py restores them after each test.
"""

import pytest

from adafruit_httpserver import MIMETypes


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("index.html", "text/html"),
        ("/static/style.css", "text/css"),
        ("script.js", "text/javascript"),
        ("data.json", "application/json"),
        ("image.png", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("archive.tar.gz", "application/gzip"),
    ],
)
def test_known_extensions(filename, mime_type):
    assert MIMETypes.get_for_filename(filename) == mime_type


def test_extension_lookup_is_case_insensitive():
    assert MIMETypes.get_for_filename("PHOTO.JPG") == "image/jpeg"


@pytest.mark.parametrize(
    "filename", ["no_extension", "file.", ".hidden", "file.unknown", "dir.html/file"]
)
def test_unknown_extension_uses_default(filename):
    assert MIMETypes.get_for_filename(filename) == MIMETypes.DEFAULT == "text/plain"


def test_default_argument():
    assert MIMETypes.get_for_filename("file.unknown", "application/x-custom") == (
        "application/x-custom"
    )
    assert MIMETypes.get_for_filename("index.html", "application/x-custom") == "text/html"


@pytest.mark.xfail(
    strict=True,
    reason="A name with no dot is looked up as an extension, so a file named 'html' is text/html",
)
def test_name_without_dot_is_not_an_extension():
    assert MIMETypes.get_for_filename("html") == MIMETypes.DEFAULT


def test_configure_default_to():
    MIMETypes.configure(default_to="application/octet-stream")

    assert MIMETypes.DEFAULT == "application/octet-stream"
    assert MIMETypes.get_for_filename("file.unknown") == "application/octet-stream"


def test_configure_keep_for():
    MIMETypes.configure(keep_for=[".html", ".css"])

    assert MIMETypes.REGISTERED == {".html": "text/html", ".css": "text/css"}
    assert MIMETypes.get_for_filename("index.html") == "text/html"
    assert MIMETypes.get_for_filename("photo.jpg") == MIMETypes.DEFAULT


def test_configure_register():
    MIMETypes.configure(register={".foo": "text/foo", ".png": "image/x-custom-png"})

    assert MIMETypes.get_for_filename("file.foo") == "text/foo"
    assert MIMETypes.get_for_filename("image.png") == "image/x-custom-png"
    assert MIMETypes.get_for_filename("index.html") == "text/html"


def test_configure_all_at_once():
    # Example from the MIMETypes.configure() docstring.
    MIMETypes.configure(
        default_to="text/plain",
        keep_for=[".jpg", ".mp4", ".txt"],
        register={".foo": "text/foo", ".bar": "text/bar", ".baz": "text/baz"},
    )

    assert set(MIMETypes.REGISTERED) == {".jpg", ".mp4", ".txt", ".foo", ".bar", ".baz"}


@pytest.mark.xfail(
    strict=True,
    reason="Lookup lowercases the extension, but register() stores it as given. So a registered "
    "uppercase extension never matches.",
)
def test_register_uppercase_extension():
    MIMETypes.configure(register={".FOO": "text/foo"})

    assert MIMETypes.get_for_filename("file.FOO") == "text/foo"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"keep_for": ["html"]},
            'Invalid extension: "html". All extensions must start with a dot.',
        ),
        ({"keep_for": [".html", ".nope"]}, 'Extension ".nope" is not registered.'),
        ({"register": {"foo": "text/foo"}}, 'Invalid extension: "foo".'),
    ],
)
def test_configure_errors_leave_registry_unchanged(kwargs, message):
    registered_before = dict(MIMETypes.REGISTERED)

    with pytest.raises(ValueError) as error:
        MIMETypes.configure(**kwargs)

    assert str(error.value).startswith(message)
    assert MIMETypes.REGISTERED == registered_before
