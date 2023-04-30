# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.request`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Dict, Tuple, Union, TYPE_CHECKING
    from socket import socket
    from socketpool import SocketPool

    if TYPE_CHECKING:
        from .server import Server
except ImportError:
    pass

import json

from .headers import Headers


class Request:
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

            request.client_address
            # ('192.168.137.1', 40684)
    """

    method: str
    """Request method e.g. "GET" or "POST"."""

    path: str
    """Path of the request, e.g. ``"/foo/bar"``."""

    query_params: Dict[str, str]
    """
    Query/GET parameters in the request.

    Example::

            request  = Request(raw_request=b"GET /?foo=bar HTTP/1.1...")
            request.query_params
            # {"foo": "bar"}
    """

    http_version: str
    """HTTP version, e.g. ``"HTTP/1.1"``."""

    headers: Headers
    """
    Headers from the request.
    """

    raw_request: bytes
    """
    Raw 'bytes' that were received from the client.

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

        if raw_request is None:
            raise ValueError("raw_request cannot be None")

        header_bytes = self._raw_header_bytes

        try:
            (
                self.method,
                self.path,
                self.query_params,
                self.http_version,
            ) = self._parse_start_line(header_bytes)
            self.headers = self._parse_headers(header_bytes)
        except Exception as error:
            raise ValueError("Unparseable raw_request: ", raw_request) from error

    @property
    def body(self) -> bytes:
        """Body of the request, as bytes."""
        return self._raw_body_bytes

    @body.setter
    def body(self, body: bytes) -> None:
        self.raw_request = self._raw_header_bytes + b"\r\n\r\n" + body

    def json(self) -> Union[dict, None]:
        """Body of the request, as a JSON-decoded dictionary."""
        return json.loads(self.body) if self.body else None

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
    def _parse_start_line(header_bytes: bytes) -> Tuple[str, str, Dict[str, str], str]:
        """Parse HTTP Start line to method, path, query_params and http_version."""

        start_line = header_bytes.decode("utf8").splitlines()[0]

        method, path, http_version = start_line.split()

        if "?" not in path:
            path += "?"

        path, query_string = path.split("?", 1)

        query_params = {}
        for query_param in query_string.split("&"):
            if "=" in query_param:
                key, value = query_param.split("=", 1)
                query_params[key] = value
            elif query_param:
                query_params[query_param] = ""

        return method, path, query_params, http_version

    @staticmethod
    def _parse_headers(header_bytes: bytes) -> Headers:
        """Parse HTTP headers from raw request."""
        header_lines = header_bytes.decode("utf8").splitlines()[1:]

        return Headers(
            {
                name: value
                for header_line in header_lines
                for name, value in [header_line.split(": ", 1)]
            }
        )
