# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.response`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Optional, Dict, Union, Tuple, Generator, Any
    from socket import socket
    from socketpool import SocketPool
except ImportError:
    pass

import os
import json
from binascii import b2a_base64
import hashlib
from errno import EAGAIN, ECONNRESET, ETIMEDOUT, ENOTCONN

from .exceptions import (
    BackslashInPathError,
    FileNotExistsError,
    ParentDirectoryReferenceError,
)
from .mime_types import MIMETypes
from .request import Request
from .status import (
    Status,
    SWITCHING_PROTOCOLS_101,
    OK_200,
    MOVED_PERMANENTLY_301,
    FOUND_302,
    TEMPORARY_REDIRECT_307,
    PERMANENT_REDIRECT_308,
)
from .headers import Headers


class Response:  # pylint: disable=too-few-public-methods
    """
    Response to a given `Request`. Use in `Server.route` handler functions.

    Base class for all other response classes.

    Example::

        @server.route(path, method)
        def route_func(request: Request):

            return Response(request, body='Some content', content_type="text/plain")
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        body: Union[str, bytes] = "",
        *,
        status: Union[Status, Tuple[int, str]] = OK_200,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
        content_type: str = None,
    ) -> None:
        """
        :param Request request: Request that this is a response to.
        :param str body: Body of response. Defaults to empty string.
        :param Status status: Status code and text. Defaults to 200 OK.
        :param Headers headers: Headers to include in response. Defaults to empty dict.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        :param str content_type: Content type of response. Defaults to None.
        """

        self._request = request
        self._body = body
        self._status = status if isinstance(status, Status) else Status(*status)
        self._headers = (
            headers.copy() if isinstance(headers, Headers) else Headers(headers)
        )
        self._cookies = cookies.copy() if cookies else {}
        self._content_type = content_type
        self._size = 0

    def _send_headers(
        self,
        content_length: Optional[int] = None,
        content_type: str = None,
    ) -> None:
        headers = self._headers.copy()

        response_message_header = (
            f"HTTP/1.1 {self._status.code} {self._status.text}\r\n"
        )

        headers.setdefault(
            "Content-Type", content_type or self._content_type or MIMETypes.DEFAULT
        )
        headers.setdefault("Content-Length", content_length)
        headers.setdefault("Connection", "close")

        for cookie_name, cookie_value in self._cookies.items():
            headers.add("Set-Cookie", f"{cookie_name}={cookie_value}")

        for header, value in headers.items():
            if value is not None:
                response_message_header += f"{header}: {value}\r\n"
        response_message_header += "\r\n"

        self._send_bytes(
            self._request.connection, response_message_header.encode("utf-8")
        )

    def _send(self) -> None:
        encoded_body = (
            self._body.encode("utf-8") if isinstance(self._body, str) else self._body
        )

        self._send_headers(len(encoded_body), self._content_type)
        self._send_bytes(self._request.connection, encoded_body)
        self._close_connection()

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
        self._size += bytes_sent

    def _close_connection(self) -> None:
        try:
            self._request.connection.close()
        except (BrokenPipeError, OSError):
            pass


class FileResponse(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for sending files.

    Instead of ``body`` it takes ``filename`` and ``root_path`` arguments.
    It is also possible to send only headers with ``head_only`` argument or modify ``buffer_size``.

    If browsers should download the file instead of displaying it, use ``as_attachment`` and
    ``download_filename`` arguments.

    Example::

        @server.route(path, method)
        def route_func(request: Request):

            return FileResponse(request, filename='index.html', root_path='/www')
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        filename: str = "index.html",
        root_path: str = None,
        *,
        status: Union[Status, Tuple[int, str]] = OK_200,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
        content_type: str = None,
        as_attachment: bool = False,
        download_filename: str = None,
        buffer_size: int = 1024,
        head_only: bool = False,
        safe: bool = True,
    ) -> None:
        """
        :param Request request: Request that this is a response to.
        :param str filename: Name of the file to send.
        :param str root_path: Path to the root directory from which to serve files. Defaults to
          server's ``root_path``.
        :param Status status: Status code and text. Defaults to ``200 OK``.
        :param Headers headers: Headers to include in response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        :param str content_type: Content type of response.
        :param bool as_attachment: If ``True``, the file will be sent as an attachment.
        :param str download_filename: Name of the file to send as an attachment.
        :param int buffer_size: Size of the buffer used to send the file. Defaults to ``1024``.
        :param bool head_only: If ``True``, only headers will be sent. Defaults to ``False``.
        :param bool safe: If ``True``, checks if ``filename`` is valid. Defaults to ``True``.
        """
        if safe:
            self._verify_file_path_is_valid(filename)

        super().__init__(
            request=request,
            headers=headers,
            cookies=cookies,
            content_type=content_type,
            status=status,
        )
        self._filename = filename + "index.html" if filename.endswith("/") else filename
        self._root_path = root_path or self._request.server.root_path
        self._full_file_path = self._combine_path(self._root_path, self._filename)
        self._content_type = content_type or MIMETypes.get_for_filename(self._filename)
        self._file_length = self._get_file_length(self._full_file_path)

        self._buffer_size = buffer_size
        self._head_only = head_only
        self._safe = safe

        if as_attachment:
            self._headers.setdefault(
                "Content-Disposition",
                f"attachment; filename={download_filename or self._filename.split('/')[-1]}",
            )

    @staticmethod
    def _verify_file_path_is_valid(file_path: str):
        """
        Verifies that ``file_path`` does not contain backslashes or parent directory references.

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
            stat = os.stat(file_path)
            st_mode, st_size = stat[0], stat[6]
            assert (st_mode & 0o170000) == 0o100000  # Check if it is a regular file
            return st_size
        except (OSError, AssertionError):
            raise FileNotExistsError(file_path)  # pylint: disable=raise-missing-from

    def _send(self) -> None:
        self._send_headers(self._file_length, self._content_type)

        if not self._head_only:
            with open(self._full_file_path, "rb") as file:
                while bytes_read := file.read(self._buffer_size):
                    self._send_bytes(self._request.connection, bytes_read)
        self._close_connection()


class ChunkedResponse(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for sending data using chunked transfer encoding.

    Instead of requiring the whole content to be passed to the constructor, it expects
    a **generator** that yields chunks of data.

    Example::

        @server.route(path, method)
        def route_func(request: Request):

            def body():
                yield "Some ch"
                yield "unked co"
                yield "ntent"

            return ChunkedResponse(request, body, content_type="text/plain")
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        body: Generator[Union[str, bytes], Any, Any],
        *,
        status: Union[Status, Tuple[int, str]] = OK_200,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
        content_type: str = None,
    ) -> None:
        """
        :param Request request: Request object
        :param Generator body: Generator that yields chunks of data.
        :param Status status: Status object or tuple with code and message.
        :param Headers headers: Headers to be sent with the response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        :param str content_type: Content type of the response.
        """

        super().__init__(
            request=request,
            headers=headers,
            cookies=cookies,
            status=status,
            content_type=content_type,
        )
        self._headers.setdefault("Transfer-Encoding", "chunked")
        self._body = body

    def _send_chunk(self, chunk: Union[str, bytes] = "") -> None:
        encoded_chunk = chunk.encode("utf-8") if isinstance(chunk, str) else chunk

        self._send_bytes(self._request.connection, b"%x\r\n" % len(encoded_chunk))
        self._send_bytes(self._request.connection, encoded_chunk)
        self._send_bytes(self._request.connection, b"\r\n")

    def _send(self) -> None:
        self._send_headers()

        for chunk in self._body():
            if 0 < len(chunk):  # Don't send empty chunks
                self._send_chunk(chunk)

        # Empty chunk to indicate end of response
        self._send_chunk()
        self._close_connection()


class JSONResponse(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for sending JSON data.

    Instead of requiring ``body`` to be passed to the constructor, it expects ``data`` to be passed
    instead.

    Example::

        @server.route(path, method)
        def route_func(request: Request):

            return JSONResponse(request, {"key": "value"})
    """

    def __init__(
        self,
        request: Request,
        data: Dict[Any, Any],
        *,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
        status: Union[Status, Tuple[int, str]] = OK_200,
    ) -> None:
        """
        :param Request request: Request that this is a response to.
        :param dict data: Data to be sent as JSON.
        :param Headers headers: Headers to include in response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        :param Status status: Status code and text. Defaults to 200 OK.
        """
        super().__init__(
            request=request,
            headers=headers,
            cookies=cookies,
            status=status,
        )
        self._data = data

    def _send(self) -> None:
        encoded_data = json.dumps(self._data).encode("utf-8")

        self._send_headers(len(encoded_data), "application/json")
        self._send_bytes(self._request.connection, encoded_data)
        self._close_connection()


class Redirect(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for redirecting to another URL.

    Instead of requiring the body to be passed to the constructor, it expects a URL to redirect to.

    Example::

        @server.route(path, method)
        def route_func(request: Request):

            return Redirect(request, "https://www.example.com")
    """

    def __init__(
        self,
        request: Request,
        url: str,
        *,
        permanent: bool = False,
        preserve_method: bool = False,
        status: Union[Status, Tuple[int, str]] = None,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
    ) -> None:
        """
        By default uses ``permament`` and ``preserve_method`` to determine the ``status`` code to
        use, but if you prefer you can specify it directly.

        Note that ``301 Moved Permanently`` and ``302 Found`` can change the method to ``GET``
        while ``307 Temporary Redirect`` and ``308 Permanent Redirect`` preserve the method.

        More information:
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Status#redirection_messages

        :param Request request: Request that this is a response to.
        :param str url: URL to redirect to.
        :param bool permanent: Whether to use a permanent redirect or a temporary one.
        :param bool preserve_method: Whether to preserve the method of the request.
        :param Status status: Status object or tuple with code and message.
        :param Headers headers: Headers to include in response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        """

        if status is not None and (permanent or preserve_method):
            raise ValueError(
                "Cannot specify both status and permanent/preserve_method argument"
            )

        if status is None:
            if preserve_method:
                status = PERMANENT_REDIRECT_308 if permanent else TEMPORARY_REDIRECT_307
            else:
                status = MOVED_PERMANENTLY_301 if permanent else FOUND_302

        super().__init__(request, status=status, headers=headers, cookies=cookies)
        self._headers.update({"Location": url})

    def _send(self) -> None:
        self._send_headers()
        self._close_connection()


class SSEResponse(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for sending Server-Sent Events.

    Allows one way communication with the client using a persistent connection.

    Keep in mind, that in order to send events, the socket must be kept open. This means that you
    have to store the response object somewhere, so you can send events to it and close it later.

    **It is very important to close the connection manually, it will not be done automatically.**

    Example::

        sse = None

        @server.route(path, method)
        def route_func(request: Request):

            # Store the response object somewhere in global scope
            global sse
            sse = SSEResponse(request)

            return sse

        ...

        # Later, when you want to send an event
        sse.send_event("Simple message")
        sse.send_event("Message", event="event_name", id=1, retry=5000)

        # Close the connection
        sse.close()
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
    ) -> None:
        """
        :param Request request: Request object
        :param Headers headers: Headers to be sent with the response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        """
        super().__init__(
            request=request,
            headers=headers,
            cookies=cookies,
            content_type="text/event-stream",
        )
        self._headers.setdefault("Cache-Control", "no-cache")
        self._headers.setdefault("Connection", "keep-alive")

    def _send(self) -> None:
        self._send_headers()

    def send_event(  # pylint: disable=too-many-arguments
        self,
        data: str,
        event: str = None,
        id: int = None,  # pylint: disable=redefined-builtin,invalid-name
        retry: int = None,
        custom_fields: Dict[str, str] = None,
    ) -> None:
        """
        Send event to the client.

        :param str data: The data to be sent.
        :param str event: (Optional) The name of the event.
        :param int id: (Optional) The event ID.
        :param int retry: (Optional) The time (in milliseconds) to wait before retrying the event.
        :param Dict[str, str] custom_fields: (Optional) Custom fields to be sent with the event.
        """
        message = f"data: {data}\n"
        if event:
            message += f"event: {event}\n"
        if id:
            message += f"id: {id}\n"
        if retry:
            message += f"retry: {retry}\n"
        if custom_fields:
            for field, value in custom_fields.items():
                message += f"{field}: {value}\n"
        message += "\n"

        self._send_bytes(self._request.connection, message.encode("utf-8"))

    def close(self):
        """
        Close the connection.

        **Always call this method when you are done sending events.**
        """
        self._send_bytes(self._request.connection, b"event: close\n")
        self._close_connection()


class Websocket(Response):  # pylint: disable=too-few-public-methods
    """
    Specialized version of `Response` class for creating a websocket connection.

    Allows two way communication between the client and the server.

    Keep in mind, that in order to send and receive messages, the socket must be kept open.
    This means that you have to store the response object somewhere, so you can send events
    to it and close it later.

    **It is very important to close the connection manually, it will not be done automatically.**

    Example::

        ws = None

        @server.route(path, method)
        def route_func(request: Request):

            # Store the response object somewhere in global scope
            global ws
            ws = Websocket(request)

            return ws

        ...

        # Receive message from client
        message = ws.receive()

        # Later, when you want to send an event
        ws.send_message("Simple message")

        # Close the connection
        ws.close()
    """

    GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    FIN = 0b10000000  # FIN bit indicating the final fragment

    # opcodes
    CONT = 0  # Continuation frame, TODO: Currently not supported
    TEXT = 1  # Frame contains UTF-8 text
    BINARY = 2  # Frame contains binary data
    CLOSE = 8  # Frame closes the connection
    PING = 9  # Frame is a ping, expecting a pong
    PONG = 10  # Frame is a pong, in response to a ping

    @staticmethod
    def _check_request_initiates_handshake(request: Request):
        if not all(
            [
                "websocket" in request.headers.get_directive("Upgrade", "").lower(),
                "upgrade" in request.headers.get_directive("Connection", "").lower(),
                "Sec-WebSocket-Key" in request.headers,
            ]
        ):
            raise ValueError("Request does not initiate websocket handshake")

    @staticmethod
    def _process_sec_websocket_key(request: Request) -> str:
        key = request.headers.get_directive("Sec-WebSocket-Key")

        if key is None:
            raise ValueError("Request does not have Sec-WebSocket-Key header")

        response_key = hashlib.new("sha1", key.encode())
        response_key.update(Websocket.GUID)

        return b2a_base64(response_key.digest()).strip().decode()

    def __init__(  # pylint: disable=too-many-arguments
        self,
        request: Request,
        headers: Union[Headers, Dict[str, str]] = None,
        cookies: Dict[str, str] = None,
        buffer_size: int = 1024,
    ) -> None:
        """
        :param Request request: Request object
        :param Headers headers: Headers to be sent with the response.
        :param Dict[str, str] cookies: Cookies to be sent with the response.
        :param int buffer_size: Size of the buffer used to send and receive messages.
        """
        self._check_request_initiates_handshake(request)

        sec_accept_key = self._process_sec_websocket_key(request)

        super().__init__(
            request=request,
            status=SWITCHING_PROTOCOLS_101,
            headers=headers,
            cookies=cookies,
        )
        self._headers.setdefault("Upgrade", "websocket")
        self._headers.setdefault("Connection", "Upgrade")
        self._headers.setdefault("Sec-WebSocket-Accept", sec_accept_key)
        self._headers.setdefault("Content-Type", None)
        self._buffer_size = buffer_size
        self.closed = False

        request.connection.setblocking(False)

    @staticmethod
    def _parse_frame_header(header):
        fin = header[0] & Websocket.FIN
        opcode = header[0] & 0b00001111
        has_mask = header[1] & 0b10000000
        length = header[1] & 0b01111111

        if length == 0b01111110:
            length = -2
        elif length == 0b01111111:
            length = -8

        return fin, opcode, has_mask, length

    def _read_frame(self):
        buffer = bytearray(self._buffer_size)

        header_length = self._request.connection.recv_into(buffer, 2)
        header_bytes = buffer[:header_length]

        fin, opcode, has_mask, length = self._parse_frame_header(header_bytes)

        # TODO: Handle continuation frames, currently not supported
        if fin != Websocket.FIN and opcode == Websocket.CONT:
            return Websocket.CONT, None

        payload = bytes()
        if fin == Websocket.FIN and opcode == Websocket.CLOSE:
            return Websocket.CLOSE, payload

        if length < 0:
            length = self._request.connection.recv_into(buffer, -length)
            length = int.from_bytes(buffer[:length], "big")

        if has_mask:
            mask_length = self._request.connection.recv_into(buffer, 4)
            mask = buffer[:mask_length]

        while 0 < length:
            payload_length = self._request.connection.recv_into(buffer, length)
            payload += buffer[: min(payload_length, length)]
            length -= min(payload_length, length)

        if has_mask:
            payload = bytes(x ^ mask[i % 4] for i, x in enumerate(payload))

        return opcode, payload

    def _handle_frame(self, opcode: int, payload: bytes) -> Union[str, bytes, None]:
        # TODO: Handle continuation frames, currently not supported
        if opcode == Websocket.CONT:
            return None

        if opcode == Websocket.CLOSE:
            self.close()
            return None

        if opcode == Websocket.PONG:
            return None
        if opcode == Websocket.PING:
            self.send_message(payload, Websocket.PONG)
            return payload

        try:
            payload = payload.decode() if opcode == Websocket.TEXT else payload
        except UnicodeError:
            pass

        return payload

    def receive(self, fail_silently: bool = False) -> Union[str, bytes, None]:
        """
        Receive a message from the client.

        :param bool fail_silently: If True, no error will be raised if the connection is closed.
        """
        if self.closed:
            if fail_silently:
                return None
            raise RuntimeError(
                "Websocket connection is closed, cannot receive messages"
            )

        try:
            opcode, payload = self._read_frame()
            frame_data = self._handle_frame(opcode, payload)

            return frame_data
        except OSError as error:
            if error.errno == EAGAIN:  # No messages available
                return None
            if error.errno == ETIMEDOUT:  # Connection timed out
                return None
            if error.errno == ENOTCONN:  # Client disconnected
                self.close()
                return None
            raise error

    @staticmethod
    def _prepare_frame(opcode: int, message: bytes) -> bytearray:
        frame = bytearray()

        frame.append(Websocket.FIN | opcode)  # Setting FIN bit

        payload_length = len(message)

        # Message under 126 bytes, use 1 byte for length
        if payload_length < 126:
            frame.append(payload_length)

        # Message between 126 and 65535 bytes, use 2 bytes for length
        elif payload_length < 65536:
            frame.append(126)
            frame.extend(payload_length.to_bytes(2, "big"))

        # Message over 65535 bytes, use 8 bytes for length
        else:
            frame.append(127)
            frame.extend(payload_length.to_bytes(8, "big"))

        frame.extend(message)
        return frame

    def send_message(
        self,
        message: Union[str, bytes],
        opcode: int = None,
        fail_silently: bool = False,
    ):
        """
        Send a message to the client.

        :param str message: Message to be sent.
        :param int opcode: Opcode of the message. Defaults to TEXT if message is a string and
                           BINARY for bytes.
        :param bool fail_silently: If True, no error will be raised if the connection is closed.
        """
        if self.closed:
            if fail_silently:
                return
            raise RuntimeError("Websocket connection is closed, cannot send message")

        determined_opcode = opcode or (
            Websocket.TEXT if isinstance(message, str) else Websocket.BINARY
        )

        if determined_opcode == Websocket.TEXT:
            message = message.encode()

        frame = self._prepare_frame(determined_opcode, message)

        try:
            self._send_bytes(self._request.connection, frame)
        except BrokenPipeError as error:
            if fail_silently:
                return
            raise error

    def _send(self) -> None:
        self._send_headers()

    def close(self):
        """
        Close the connection.

        **Always call this method when you are done sending events.**
        """
        if not self.closed:
            self.send_message(b"", Websocket.CLOSE, fail_silently=True)
            self._close_connection()
            self.closed = True
