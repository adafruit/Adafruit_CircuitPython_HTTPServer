try:
    from typing import Any, Optional
except ImportError:
    pass

from errno import EAGAIN, ECONNRESET
import os

from .mime_type import MIMEType
from .status import HTTPStatus

class HTTPResponse:
    """Details of an HTTP response. Use in `HTTPServer.route` decorator functions."""

    _HEADERS_FORMAT = (
        "HTTP/1.1 {}\r\n"
        "Content-Type: {}\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    def __init__(
        self,
        *,
        status: tuple = HTTPStatus.OK,
        content_type: str = MIMEType.TEXT_PLAIN,
        body: str = "",
        filename: Optional[str] = None,
        root: str = "",
    ) -> None:
        """Create an HTTP response.

        :param tuple status: The HTTP status code to return, as a tuple of (int, "message").
          Common statuses are available in `HTTPStatus`.
        :param str content_type: The MIME type of the data being returned.
          Common MIME types are available in `MIMEType`.
        :param Union[str|bytes] body:
          The data to return in the response body, if ``filename`` is not ``None``.
        :param str filename: If not ``None``,
          return the contents of the specified file, and ignore ``body``.
        :param str root: root directory for filename, without a trailing slash
        """
        self.status = status
        self.content_type = content_type
        self.body = body.encode() if isinstance(body, str) else body
        self.filename = filename

        self.root = root

    def send(self, conn: Any) -> None:
        # TODO: Use Union[SocketPool.Socket | socket.socket] for the type annotation in some way.
        """Send the constructed response over the given socket."""
        if self.filename:
            try:
                file_length = os.stat(self.root + self.filename)[6]
                self._send_file_response(conn, self.filename, self.root, file_length)
            except OSError:
                self._send_response(
                    conn,
                    HTTPStatus.NOT_FOUND,
                    MIMEType.TEXT_PLAIN,
                    f"{HTTPStatus.NOT_FOUND} {self.filename}\r\n",
                )
        else:
            self._send_response(conn, self.status, self.content_type, self.body)

    def _send_response(self, conn, status, content_type, body):
        self._send_bytes(
            conn, self._HEADERS_FORMAT.format(status, content_type, len(body))
        )
        self._send_bytes(conn, body)

    def _send_file_response(self, conn, filename, root, file_length):
        self._send_bytes(
            conn,
            self._HEADERS_FORMAT.format(
                self.status, MIMEType.mime_type(filename), file_length
            ),
        )
        with open(root + filename, "rb") as file:
            while bytes_read := file.read(2048):
                self._send_bytes(conn, bytes_read)

    @staticmethod
    def _send_bytes(conn, buf):
        bytes_sent = 0
        bytes_to_send = len(buf)
        view = memoryview(buf)
        while bytes_sent < bytes_to_send:
            try:
                bytes_sent += conn.send(view[bytes_sent:])
            except OSError as exc:
                if exc.errno == EAGAIN:
                    continue
                if exc.errno == ECONNRESET:
                    return
