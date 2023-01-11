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

                # or

                response = HTTPResponse(request)
                with response:
                    response.send(body='Some content', content_type="text/plain")

                # or

                with HTTPResponse(request) as response:
                    response.send("Some content", content_type="text/plain")

            # Response with 'Transfer-Encoding: chunked' header
            @server.route(path, method)
            def route_func(request):

                response = HTTPResponse(request, content_type="text/plain", chunked=True)
                with response:
                    response.send_chunk("Some content")
                    response.send_chunk("Some more content")

                # or

                with HTTPResponse(request, content_type="text/plain", chunked=True) as response:
                    response.send_chunk("Some content")
                    response.send_chunk("Some more content")
    """

    request: HTTPRequest
    """The request that this is a response to."""

    http_version: str
    status: HTTPStatus
    headers: HTTPHeaders
    content_type: str
    """
    Defaults to ``text/plain`` if not set.

    Can be explicitly provided in the constructor, in `send()` or
    implicitly determined from filename in `send_file()`.

    Common MIME types are defined in `adafruit_httpserver.mime_type.MIMEType`.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: HTTPRequest,
        status: Union[HTTPStatus, Tuple[int, str]] = CommonHTTPStatus.OK_200,
        headers: Union[HTTPHeaders, Dict[str, str]] = None,
        content_type: str = None,
        http_version: str = "HTTP/1.1",
        chunked: bool = False,
    ) -> None:
        """
        Creates an HTTP response.

        Sets `status`, ``headers`` and `http_version`
        and optionally default ``content_type``.

        To send the response, call `send` or `send_file`.
        For chunked response use
        ``with HTTPRequest(request, content_type=..., chunked=True) as r:`` and `send_chunk`.
        """
        self.request = request
        self.status = status if isinstance(status, HTTPStatus) else HTTPStatus(*status)
        self.headers = (
            headers.copy() if isinstance(headers, HTTPHeaders) else HTTPHeaders(headers)
        )
        self.content_type = content_type
        self.http_version = http_version
        self.chunked = chunked
        self._response_already_sent = False

    def _send_headers(
        self,
        content_length: Optional[int] = None,
        content_type: str = None,
    ) -> None:
        """
        Sends headers.
        Implicitly called by `send` and `send_file` and in
        ``with HTTPResponse(request, chunked=True) as response:`` context manager.
        """
        headers = self.headers.copy()

        response_message_header = (
            f"{self.http_version} {self.status.code} {self.status.text}\r\n"
        )

        headers.setdefault(
            "Content-Type", content_type or self.content_type or MIMEType.TYPE_TXT
        )
        headers.setdefault("Connection", "close")
        if self.chunked:
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
        content_type: str = None,
    ) -> None:
        """
        Sends response with content built from ``body``.
        Implicitly calls ``_send_headers`` before sending the body.

        Should be called **only once** per response.
        """
        if self._response_already_sent:
            raise RuntimeError("Response was already sent")

        if getattr(body, "encode", None):
            encoded_response_message_body = body.encode("utf-8")
        else:
            encoded_response_message_body = body

        self._send_headers(
            content_type=content_type or self.content_type,
            content_length=len(encoded_response_message_body),
        )
        self._send_bytes(self.request.connection, encoded_response_message_body)
        self._response_already_sent = True

    def send_file(
        self,
        filename: str = "index.html",
        root_path: str = "./",
    ) -> None:
        """
        Send response with content of ``filename`` located in ``root_path``.
        Implicitly calls ``_send_headers`` before sending the file content.

        Should be called **only once** per response.
        """
        if self._response_already_sent:
            raise RuntimeError("Response was already sent")

        if not root_path.endswith("/"):
            root_path += "/"
        try:
            file_length = os.stat(root_path + filename)[6]
        except OSError:
            # If the file doesn't exist, return 404.
            HTTPResponse(self.request, status=CommonHTTPStatus.NOT_FOUND_404).send()
            return

        self._send_headers(
            content_type=MIMEType.from_file_name(filename),
            content_length=file_length,
        )

        with open(root_path + filename, "rb") as file:
            while bytes_read := file.read(2048):
                self._send_bytes(self.request.connection, bytes_read)
        self._response_already_sent = True

    def send_chunk(self, chunk: str = "") -> None:
        """
        Sends chunk of response.

        Should be used **only** inside
        ``with HTTPResponse(request, chunked=True) as response:`` context manager.

        :param str chunk: String data to be sent.
        """
        if getattr(chunk, "encode", None):
            chunk = chunk.encode("utf-8")

        self._send_bytes(self.request.connection, b"%x\r\n" % len(chunk))
        self._send_bytes(self.request.connection, chunk)
        self._send_bytes(self.request.connection, b"\r\n")

    def __enter__(self):
        if self.chunked:
            self._send_headers()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            return False

        if self.chunked:
            self.send_chunk("")
        return True

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
