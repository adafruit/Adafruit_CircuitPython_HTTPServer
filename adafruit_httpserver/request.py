# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.request`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import List, Dict, Tuple, Union, Any, TYPE_CHECKING
    from socket import socket
    from socketpool import SocketPool

    if TYPE_CHECKING:
        from .server import Server
except ImportError:
    pass

import json

from .headers import Headers
from .interfaces import _IFieldStorage, _IXSSSafeFieldStorage
from .methods import POST, PUT, PATCH, DELETE


class QueryParams(_IXSSSafeFieldStorage):
    """
    Class for parsing and storing GET query parameters requests.

    Examples::

        query_params = QueryParams("foo=bar&baz=qux&baz=quux")
        # QueryParams({"foo": ["bar"], "baz": ["qux", "quux"]})

        query_params.get("foo") # "bar"
        query_params["foo"] # "bar"
        query_params.get("non-existent-key") # None
        query_params.get_list("baz") # ["qux", "quux"]
        "unknown-key" in query_params # False
        query_params.fields # ["foo", "baz"]
    """

    _storage: Dict[str, List[str]]

    def __init__(self, query_string: str) -> None:
        self._storage = {}

        for query_param in query_string.split("&"):
            if "=" in query_param:
                key, value = query_param.split("=", 1)
                self._add_field_value(key, value)
            elif query_param:
                self._add_field_value(query_param, "")

    def _add_field_value(self, field_name: str, value: str) -> None:
        super()._add_field_value(field_name, value)

    def get(
        self, field_name: str, default: str = None, *, safe=True
    ) -> Union[str, None]:
        return super().get(field_name, default, safe=safe)

    def get_list(self, field_name: str, *, safe=True) -> List[str]:
        return super().get_list(field_name, safe=safe)


class File:
    """
    Class representing a file uploaded via POST.

    Examples::

        file = request.form_data.files.get("uploaded_file")
        # File(filename="foo.txt", content_type="text/plain", size=14)

        file.content
        # "Hello, world!\\n"
    """

    filename: str
    """Filename of the file."""

    content_type: str
    """Content type of the file."""

    content: Union[str, bytes]
    """Content of the file."""

    def __init__(
        self, filename: str, content_type: str, content: Union[str, bytes]
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.content = content

    @property
    def content_bytes(self) -> bytes:
        """
        Content of the file as bytes.
        It is recommended to use this instead of ``content`` as it will always return bytes.

        Example::

            file = request.form_data.files.get("uploaded_file")

            with open(file.filename, "wb") as f:
                f.write(file.content_bytes)
        """
        return (
            self.content.encode("utf-8")
            if isinstance(self.content, str)
            else self.content
        )

    @property
    def size(self) -> int:
        """Length of the file content."""
        return len(self.content)

    def __repr__(self) -> str:
        filename, content_type, size = (
            repr(self.filename),
            repr(self.content_type),
            repr(self.size),
        )
        return f"{self.__class__.__name__}({filename=}, {content_type=}, {size=})"


class Files(_IFieldStorage):
    """Class for files uploaded via POST."""

    _storage: Dict[str, List[File]]

    def __init__(self) -> None:
        self._storage = {}

    def _add_field_value(self, field_name: str, value: File) -> None:
        super()._add_field_value(field_name, value)

    def get(self, field_name: str, default: Any = None) -> Union[File, Any, None]:
        return super().get(field_name, default)

    def get_list(self, field_name: str) -> List[File]:
        return super().get_list(field_name)


class FormData(_IXSSSafeFieldStorage):
    """
    Class for parsing and storing form data from POST requests.

    Supports ``application/x-www-form-urlencoded``, ``multipart/form-data`` and ``text/plain``
    content types.

    Examples::

        form_data = FormData(b"foo=bar&baz=qux&baz=quuz", "application/x-www-form-urlencoded")
        # or
        form_data = FormData(b"foo=bar\\r\\nbaz=qux\\r\\nbaz=quux", "text/plain")
        # FormData({"foo": ["bar"], "baz": ["qux", "quux"]})

        form_data.get("foo") # "bar"
        form_data["foo"] # "bar"
        form_data.get("non-existent-key") # None
        form_data.get_list("baz") # ["qux", "quux"]
        "unknown-key" in form_data # False
        form_data.fields # ["foo", "baz"]
    """

    _storage: Dict[str, List[Union[str, bytes]]]
    files: Files

    @staticmethod
    def _check_is_supported_content_type(content_type: str) -> None:
        return content_type in (
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
        )

    def __init__(self, data: bytes, headers: Headers, *, debug: bool = False) -> None:
        self._storage = {}
        self.files = Files()

        self.content_type = headers.get_directive("Content-Type")
        content_length = int(headers.get("Content-Length", 0))

        if debug and not self._check_is_supported_content_type(self.content_type):
            _debug_unsupported_form_content_type(self.content_type)

        if self.content_type == "application/x-www-form-urlencoded":
            self._parse_x_www_form_urlencoded(data[:content_length])

        elif self.content_type == "multipart/form-data":
            boundary = headers.get_parameter("Content-Type", "boundary")
            self._parse_multipart_form_data(data[:content_length], boundary)

        elif self.content_type == "text/plain":
            self._parse_text_plain(data[:content_length])

    def _parse_x_www_form_urlencoded(self, data: bytes) -> None:
        if not (decoded_data := data.decode("utf-8").strip("&")):
            return

        for field_name, value in [
            key_value.split("=", 1) if "=" in key_value else (key_value, "")
            for key_value in decoded_data.split("&")
        ]:
            self._add_field_value(field_name, value)

    def _parse_multipart_form_data(self, data: bytes, boundary: str) -> None:
        blocks = data.split(b"--" + boundary.encode())[1:-1]

        for block in blocks:
            header_bytes, content_bytes = block.split(b"\r\n\r\n", 1)
            headers = Headers(header_bytes.decode("utf-8").strip())

            field_name = headers.get_parameter("Content-Disposition", "name")
            filename = headers.get_parameter("Content-Disposition", "filename")
            content_type = headers.get_directive("Content-Type", "text/plain")
            charset = headers.get_parameter("Content-Type", "charset", "utf-8")

            content = content_bytes[:-2]  # remove trailing \r\n
            value = content.decode(charset) if content_type == "text/plain" else content

            # TODO: Other text content types (e.g. application/json) should be decoded as well and

            if filename is not None:
                self.files._add_field_value(  # pylint: disable=protected-access
                    field_name, File(filename, content_type, value)
                )
            else:
                self._add_field_value(field_name, value)

    def _parse_text_plain(self, data: bytes) -> None:
        lines = data.decode("utf-8").split("\r\n")[:-1]

        for line in lines:
            field_name, value = line.split("=", 1)

            self._add_field_value(field_name, value)

    def _add_field_value(self, field_name: str, value: Union[str, bytes]) -> None:
        super()._add_field_value(field_name, value)

    def get(
        self, field_name: str, default: Union[str, bytes] = None, *, safe=True
    ) -> Union[str, bytes, None]:
        return super().get(field_name, default, safe=safe)

    def get_list(self, field_name: str, *, safe=True) -> List[Union[str, bytes]]:
        return super().get_list(field_name, safe=safe)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({repr(self._storage)}, files={repr(self.files._storage)})"


class Request:  # pylint: disable=too-many-instance-attributes
    """
    Incoming request, constructed from raw incoming bytes.
    It is passed as first argument to all route handlers.
    """

    server: "Server"
    """
    Server object that received the request.
    """

    connection: Union["SocketPool.Socket", "socket.socket"]
    """
    Socket object used to send and receive data on the connection.
    """

    client_address: Tuple[str, int]
    """
    Address and port bound to the socket on the other end of the connection.

    Example::

        request.client_address  # ('192.168.137.1', 40684)
    """

    method: str
    """Request method e.g. "GET" or "POST"."""

    path: str
    """Path of the request, e.g. ``"/foo/bar"``."""

    query_params: QueryParams
    """
    Query/GET parameters in the request.

    Example::

        request  = Request(..., raw_request=b"GET /?foo=bar&baz=qux HTTP/1.1...")

        request.query_params                  # QueryParams({"foo": "bar"})
        request.query_params["foo"]           # "bar"
        request.query_params.get_list("baz")  # ["qux"]
    """

    http_version: str
    """HTTP version, e.g. ``"HTTP/1.1"``."""

    headers: Headers
    """
    Headers from the request.
    """

    raw_request: bytes
    """
    Raw ``bytes`` that were received from the client.

    Should **not** be modified directly.
    """

    def __init__(
        self,
        server: "Server",
        connection: Union["SocketPool.Socket", "socket.socket"],
        client_address: Tuple[str, int],
        raw_request: bytes = None,
    ) -> None:
        self.server = server
        self.connection = connection
        self.client_address = client_address
        self.raw_request = raw_request
        self._form_data = None
        self._cookies = None

        if raw_request is None:
            raise ValueError("raw_request cannot be None")

        try:
            (
                self.method,
                self.path,
                self.query_params,
                self.http_version,
                self.headers,
            ) = self._parse_request_header(self._raw_header_bytes)
        except Exception as error:
            raise ValueError("Unparseable raw_request: ", raw_request) from error

    @property
    def body(self) -> bytes:
        """Body of the request, as bytes."""
        return self._raw_body_bytes

    @body.setter
    def body(self, body: bytes) -> None:
        self.raw_request = self._raw_header_bytes + b"\r\n\r\n" + body

    @staticmethod
    def _parse_cookies(cookie_header: str) -> None:
        """Parse cookies from headers."""
        if cookie_header is None:
            return {}

        return {
            name: value.strip('"')
            for name, value in [
                cookie.strip().split("=", 1) for cookie in cookie_header.split(";")
            ]
        }

    @property
    def cookies(self) -> Dict[str, str]:
        """
        Cookies sent with the request.

        Example::

            request.headers["Cookie"]
            # "foo=bar; baz=qux; foo=quux"

            request.cookies
            # {"foo": "quux", "baz": "qux"}
        """
        if self._cookies is None:
            self._cookies = self._parse_cookies(self.headers.get("Cookie"))
        return self._cookies

    @property
    def form_data(self) -> Union[FormData, None]:
        """
        POST data of the request.

        Example::

            # application/x-www-form-urlencoded
            request = Request(...,
                raw_request=b\"\"\"...
                foo=bar&baz=qux\"\"\"
            )

            # or

            # multipart/form-data
            request = Request(...,
                raw_request=b\"\"\"...
                --boundary
                Content-Disposition: form-data; name="foo"

                bar
                --boundary
                Content-Disposition: form-data; name="baz"

                qux
                --boundary--\"\"\"
            )

            # or

            # text/plain
            request = Request(...,
                raw_request=b\"\"\"...
                foo=bar
                baz=qux
                \"\"\"
            )

            request.form_data                  # FormData({'foo': ['bar'], 'baz': ['qux']})
            request.form_data["foo"]           # "bar"
            request.form_data.get_list("baz")  # ["qux"]
        """
        if self._form_data is None and self.method == "POST":
            self._form_data = FormData(self.body, self.headers, debug=self.server.debug)
        return self._form_data

    def json(self) -> Union[dict, None]:
        """
        Body of the request, as a JSON-decoded dictionary.
        Only available for POST, PUT, PATCH and DELETE requests.
        """
        return (
            json.loads(self.body)
            if (self.body and self.method in (POST, PUT, PATCH, DELETE))
            else None
        )

    @property
    def _raw_header_bytes(self) -> bytes:
        """Returns headers bytes."""
        empty_line_index = self.raw_request.find(b"\r\n\r\n")

        return self.raw_request[:empty_line_index]

    @property
    def _raw_body_bytes(self) -> bytes:
        """Returns body bytes."""
        empty_line_index = self.raw_request.find(b"\r\n\r\n")

        return self.raw_request[empty_line_index + 4 :]

    @staticmethod
    def _parse_request_header(
        header_bytes: bytes,
    ) -> Tuple[str, str, QueryParams, str, Headers]:
        """Parse HTTP Start line to method, path, query_params and http_version."""

        start_line, headers_string = (
            header_bytes.decode("utf-8").strip().split("\r\n", 1)
        )

        method, path, http_version = start_line.strip().split()

        if "?" not in path:
            path += "?"

        path, query_string = path.split("?", 1)

        query_params = QueryParams(query_string)
        headers = Headers(headers_string)

        return method, path, query_params, http_version, headers


def _debug_unsupported_form_content_type(content_type: str) -> None:
    """Warns when an unsupported form content type is used."""
    print(
        f"WARNING: Unsupported Content-Type: {content_type}. "
        "Only `application/x-www-form-urlencoded`, `multipart/form-data` and `text/plain` are "
        "supported."
    )
