# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.response.HTTPResponse`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Optional, Dict, Union, Tuple
    from socket import socket
    from socketpool import SocketPool
except ImportError:
    pass

import os
from errno import EAGAIN, ECONNRESET

from .mime_type import MIMEType
from .request import HTTPRequest
from .status import HTTPStatus, CommonHTTPStatus
from .headers import HTTPHeaders


class HTTPResponse:
    """
    Response to a given `HTTPRequest`. Use in `HTTPServer.route` decorator functions.

    Example::

            # Response with 'Content-Length' header
            @server.route(path, method)
            def route_func(request):
                response = HTTPResponse(request)
                response.send("Some content", content_type="text/plain")

            # Response with 'Transfer-Encoding: chunked' header
            @server.route(path, method)
            def route_func(request):
                response = HTTPResponse(request, content_type="text/html")
                response.send_headers(content_type="text/plain", chunked=True)
                response.send_body_chunk("Some content")
                response.send_body_chunk("Some more content")
                response.send_body_chunk("")  # Send empty packet to finish chunked stream
    """

    request: HTTPRequest
    """The request that this is a response to."""

    http_version: str
    status: HTTPStatus
    headers: HTTPHeaders

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: HTTPRequest,
        status: Union[HTTPStatus, Tuple[int, str]] = CommonHTTPStatus.OK_200,
        headers: Union[HTTPHeaders, Dict[str, str]] = None,
        http_version: str = "HTTP/1.1",
    ) -> None:
        """
        Creates an HTTP response.

        Sets `status`, ``headers`` and `http_version`.

        To send the response, call `send` or `send_file`.
        For chunked response ``send_headers(chunked=True)`` and then `send_chunk_body`.
        """
        self.request = request
        self.status = status if isinstance(status, HTTPStatus) else HTTPStatus(*status)
        self.headers = (
            headers.copy() if isinstance(headers, HTTPHeaders) else HTTPHeaders(headers)
        )
        self.http_version = http_version

    def send_headers(
        self,
        content_length: Optional[int] = None,
        content_type: str = MIMEType.TYPE_TXT,
        chunked: bool = False,
    ) -> None:
        """
        Send response with `body` over the given socket.
        """
        headers = self.headers.copy()

        response_message_header = (
            f"{self.http_version} {self.status.code} {self.status.text}\r\n"
        )

        headers.setdefault("Content-Type", content_type)
        headers.setdefault("Connection", "close")
        if chunked:
            headers.setdefault("Transfer-Encoding", "chunked")
        else:
            headers.setdefault("Content-Length", content_length)

        for header, value in headers.items():
            response_message_header += f"{header}: {value}\r\n"
        response_message_header += "\r\n"

        self._send_bytes(
            self.request.connection, response_message_header.encode("utf-8")
        )

    def send(
        self,
        body: str = "",
        content_type: str = MIMEType.TYPE_TXT,
    ) -> None:
        """
        Send response with `body` over the given socket.
        Implicitly calls `send_headers` before sending the body.
        """
        encoded_response_message_body = body.encode("utf-8")

        self.send_headers(
            content_type=content_type,
            content_length=len(encoded_response_message_body),
        )
        self._send_bytes(self.request.connection, encoded_response_message_body)

    def send_file(
        self,
        filename: str = "index.html",
        root_path: str = "./",
    ) -> None:
        """
        Send response with content of ``filename`` located in ``root_path`` over the given socket.
        """
        if not root_path.endswith("/"):
            root_path += "/"
        try:
            file_length = os.stat(root_path + filename)[6]
        except OSError:
            # If the file doesn't exist, return 404.
            HTTPResponse(self.request, status=CommonHTTPStatus.NOT_FOUND_404).send()
            return

        self.send_headers(
            content_type=MIMEType.from_file_name(filename),
            content_length=file_length,
        )

        with open(root_path + filename, "rb") as file:
            while bytes_read := file.read(2048):
                self._send_bytes(self.request.connection, bytes_read)

    def send_chunk_body(self, chunk: str = "") -> None:
        """
        Send chunk of data to the given socket.

        Call without `chunk` to finish the session.

        :param str chunk: String data to be sent.
        """
        hex_length = hex(len(chunk)).lstrip("0x").rstrip("L")

        self._send_bytes(
            self.request.connection, f"{hex_length}\r\n{chunk}\r\n".encode("utf-8")
        )

    @staticmethod
    def _send_bytes(
        conn: Union["SocketPool.Socket", "socket.socket"],
        buffer: Union[bytes, bytearray, memoryview],
    ):
        bytes_sent = 0
        bytes_to_send = len(buffer)
        view = memoryview(buffer)
        while bytes_sent < bytes_to_send:
            try:
                bytes_sent += conn.send(view[bytes_sent:])
            except OSError as exc:
                if exc.errno == EAGAIN:
                    continue
                if exc.errno == ECONNRESET:
                    return
