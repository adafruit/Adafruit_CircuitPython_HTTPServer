# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.response`
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

from .exceptions import (
    BackslashInPathError,
    FileNotExistsError,
    ParentDirectoryReferenceError,
    ResponseAlreadySentError,
)
from .mime_types import MIMETypes
from .request import Request
from .status import Status, OK_200
from .headers import Headers


class Response:
    """
    Response to a given `Request`. Use in `Server.route` handler functions.

    Example::

        # Response with 'Content-Length' header
        @server.route(path, method)
        def route_func(request):

            response = Response(request)
            response.send("Some content", content_type="text/plain")

            # or

            response = Response(request)
            with response:
                response.send(body='Some content', content_type="text/plain")

            # or

            with Response(request) as response:
                response.send("Some content", content_type="text/plain")

        # Response with 'Transfer-Encoding: chunked' header
        @server.route(path, method)
        def route_func(request):

            response = Response(request, content_type="text/plain", chunked=True)
            with response:
                response.send_chunk("Some content")
                response.send_chunk("Some more content")

            # or

            with Response(request, content_type="text/plain", chunked=True) as response:
                response.send_chunk("Some content")
                response.send_chunk("Some more content")
    """

    request: Request
    """The request that this is a response to."""

    http_version: str

    status: Status
    """Status code of the response. Defaults to ``200 OK``."""

    headers: Headers
    """Headers to be sent in the response."""

    content_type: str
    """
    Defaults to ``text/plain`` if not set.

    Can be explicitly provided in the constructor, in ``send()`` or
    implicitly determined from filename in ``send_file()``.

    Common MIME types are defined in `adafruit_httpserver.mime_types`.
    """

    size: int = 0
    """Size of the response in bytes."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        status: Union[Status, Tuple[int, str]] = OK_200,
        headers: Union[Headers, Dict[str, str]] = None,
        content_type: str = None,
        http_version: str = "HTTP/1.1",
        chunked: bool = False,
    ) -> None:
        """
        Creates an HTTP response.

        Sets `status`, ``headers`` and `http_version`
        and optionally default ``content_type``.

        To send the response, call ``send`` or ``send_file``.
        For chunked response use
        ``with Response(request, content_type=..., chunked=True) as r:`` and `send_chunk`.
        """
        self.request = request
        self.status = status if isinstance(status, Status) else Status(*status)
        self.headers = (
            headers.copy() if isinstance(headers, Headers) else Headers(headers)
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
        Implicitly called by ``send`` and ``send_file`` and in
        ``with Response(request, chunked=True) as response:`` context manager.
        """
        headers = self.headers.copy()

        response_message_header = (
            f"{self.http_version} {self.status.code} {self.status.text}\r\n"
        )

        headers.setdefault(
            "Content-Type", content_type or self.content_type or MIMETypes.DEFAULT
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

    def _check_if_not_already_sent(self) -> None:
        """Prevents calling ``send`` or ``send_file`` more than once."""
        if self._response_already_sent:
            raise ResponseAlreadySentError

    def _check_chunked(self, expected_value: bool) -> None:
        """Prevents calling incompatible methods on chunked/non-chunked response."""
        if self.chunked != expected_value:
            raise RuntimeError(
                "Trying to send non-chunked data in chunked response."
                if self.chunked
                else "Trying to send chunked data in non-chunked response."
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
        self._check_if_not_already_sent()
        self._check_chunked(False)

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

        if self.request.server.debug:
            _debug_response_sent(self)

    @staticmethod
    def _check_file_path_is_valid(file_path: str) -> bool:
        """
        Checks if ``file_path`` does not contain backslashes or parent directory references.

        If not raises error corresponding to the problem.
        """

        # Check for backslashes
        if "\\" in file_path:  # pylint: disable=anomalous-backslash-in-string
            raise BackslashInPathError(file_path)

        # Check each component of the path for parent directory references
        for part in file_path.split("/"):
            if part == "..":
                raise ParentDirectoryReferenceError(file_path)

    @staticmethod
    def _combine_path(root_path: str, filename: str) -> str:
        """
        Combines ``root_path`` and ``filename`` into a single path.
        """

        if not root_path.endswith("/"):
            root_path += "/"
        if filename.startswith("/"):
            filename = filename[1:]

        return root_path + filename

    @staticmethod
    def _get_file_length(file_path: str) -> int:
        """
        Tries to get the length of the file at ``file_path``.
        Raises ``FileNotExistsError`` if file does not exist.
        """
        try:
            return os.stat(file_path)[6]
        except OSError:
            raise FileNotExistsError(file_path)  # pylint: disable=raise-missing-from

    def send_file(  # pylint: disable=too-many-arguments
        self,
        filename: str = "index.html",
        root_path: str = None,
        buffer_size: int = 1024,
        head_only: bool = False,
        safe: bool = True,
    ) -> None:
        """
        Send response with content of ``filename`` located in ``root_path``.
        Implicitly calls ``_send_headers`` before sending the file content.
        File is send split into ``buffer_size`` parts.

        Should be called **only once** per response.
        """
        self._check_if_not_already_sent()
        self._check_chunked(False)

        if safe:
            self._check_file_path_is_valid(filename)

        root_path = root_path or self.request.server.root_path
        full_file_path = self._combine_path(root_path, filename)

        file_length = self._get_file_length(full_file_path)

        self._send_headers(
            content_type=MIMETypes.get_for_filename(filename),
            content_length=file_length,
        )

        if not head_only:
            with open(full_file_path, "rb") as file:
                while bytes_read := file.read(buffer_size):
                    self._send_bytes(self.request.connection, bytes_read)
        self._response_already_sent = True

        if self.request.server.debug:
            _debug_response_sent(self)

    def send_chunk(self, chunk: str = "") -> None:
        """
        Sends chunk of response.

        Should be used **only** inside
        ``with Response(request, chunked=True) as response:`` context manager.

        :param str chunk: String data to be sent.
        """
        self._check_if_not_already_sent()
        self._check_chunked(True)

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
        self._response_already_sent = True

        if self.chunked and self.request.server.debug:
            _debug_response_sent(self)

        return True

    def _send_bytes(
        self,
        conn: Union["SocketPool.Socket", "socket.socket"],
        buffer: Union[bytes, bytearray, memoryview],
    ):
        bytes_sent: int = 0
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
                raise
        self.size += bytes_sent


def _debug_response_sent(response: "Response"):
    """Prints a message when after a response is sent."""
    client_ip = response.request.client_address[0]
    method = response.request.method
    path = response.request.path
    req_size = len(response.request.raw_request)
    status = response.status
    res_size = response.size

    print(f'{client_ip} -- "{method} {path}" {req_size} -- "{status}" {res_size}')
