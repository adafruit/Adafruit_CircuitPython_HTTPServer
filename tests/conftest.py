# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Shared fixtures for the adafruit_httpserver tests.

The tests run on CPython. Run them from the repository root with::

    python -m pytest

Two ways of driving the library:

- Real sockets: ``make_server`` starts a ``Server`` on 127.0.0.1 with an OS-assigned
  port, and ``http`` sends it a raw request, calls ``poll()`` once, and returns the reply.
  Single-threaded: the client's bytes are already queued in the kernel when ``poll()`` runs.
- Fake sockets: ``fake_socket`` and ``fake_pool`` return in-memory stand-ins for error
  paths that are hard to cause with real sockets. Examples are EAGAIN (no data yet on a
  non-blocking socket), ECONNRESET (connection reset by the peer), and partial sends.

Helpers that tests construct directly (``FakeSocket``, ``FakePool``) are returned by
fixtures as classes, so test modules do not need to import from this file.
"""

import errno
import shutil
import socket
import subprocess

import pytest

from adafruit_httpserver import MIMETypes, Request, Server

CLIENT_ADDRESS = ("127.0.0.1", 54321)


class FakeSocket:
    """
    In-memory connection socket.

    ``recv_into()`` returns queued byte chunks in order, splitting a chunk if the buffer is
    smaller. A queued exception instance is raised instead of returning data.

    When the queue is empty, ``recv_into()`` returns 0 (peer closed) if ``eof`` is true.
    Otherwise it raises ``OSError(EAGAIN)``, like a non-blocking socket with no data.

    ``send()`` appends to ``sent``. Two arguments change its behavior:

    - ``max_send`` limits how many bytes each call accepts, to exercise partial sends.
    - ``send_errors`` is a list with one entry per ``send()`` call. An exception instance
      is raised. ``None`` means send normally.
    """

    def __init__(self, recv_chunks=(), *, eof=True, max_send=None, send_errors=()):
        self._recv_queue = list(recv_chunks)
        self.eof = eof
        self.max_send = max_send
        self._send_errors = list(send_errors)
        self.sent = bytearray()
        self.send_calls = 0
        self.closed = False
        self.blocking = True
        self.timeout = None

    def feed(self, *chunks):
        """Queue more data (or exceptions) for ``recv_into()``."""
        self._recv_queue.extend(chunks)

    def recv_into(self, buffer, nbytes=0):
        if not self._recv_queue:
            if self.eof:
                return 0
            raise OSError(errno.EAGAIN, "no data")

        item = self._recv_queue[0]
        if isinstance(item, BaseException):
            self._recv_queue.pop(0)
            raise item

        limit = min(nbytes or len(buffer), len(buffer))
        count = min(len(item), limit)
        buffer[:count] = item[:count]

        if count < len(item):
            self._recv_queue[0] = item[count:]
        else:
            self._recv_queue.pop(0)
        return count

    def send(self, data):
        self.send_calls += 1
        if self._send_errors:
            error = self._send_errors.pop(0)
            if error is not None:
                raise error

        data = bytes(data)
        count = len(data) if self.max_send is None else min(len(data), self.max_send)
        self.sent += data[:count]
        return count

    def settimeout(self, value):
        self.timeout = value

    def setblocking(self, flag):
        self.blocking = flag

    def close(self):
        self.closed = True


class FakeListener:
    """
    In-memory listening socket returned by ``FakePool.socket()``.

    ``accept()`` returns queued ``(FakeSocket, address)`` pairs in order, or raises a queued
    exception instance. When the queue is empty it raises ``OSError(EAGAIN)``, like a
    non-blocking listening socket with no pending connection.
    """

    def __init__(self, accepts=()):
        self._accept_queue = list(accepts)
        self.bound_to = None
        self.closed = False

    def accept(self):
        if not self._accept_queue:
            raise OSError(errno.EAGAIN, "no pending connection")
        item = self._accept_queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def setsockopt(self, level, optname, value):
        pass

    def bind(self, address):
        self.bound_to = address

    def listen(self, backlog):
        pass

    def setblocking(self, flag):
        pass

    def close(self):
        self.closed = True


class FakePool:
    """
    Socket source for ``Server`` that hands out a single ``FakeListener``.

    ``accepts`` is passed to the listener. Items may be ``FakeSocket`` instances (paired
    with a default client address) or exception instances.
    """

    AF_INET = socket.AF_INET
    SOCK_STREAM = socket.SOCK_STREAM
    SOL_SOCKET = socket.SOL_SOCKET
    SO_REUSEADDR = socket.SO_REUSEADDR

    def __init__(self, accepts=(), *, getaddrinfo_error=None):
        self.listener = FakeListener(
            (item, CLIENT_ADDRESS) if isinstance(item, FakeSocket) else item for item in accepts
        )
        self._getaddrinfo_error = getaddrinfo_error

    def socket(self, family=None, type=None, proto=0):
        return self.listener

    def getaddrinfo(self, host, port, family=0, type=0, proto=0, flags=0):
        if self._getaddrinfo_error is not None:
            raise self._getaddrinfo_error
        return [(self.AF_INET, self.SOCK_STREAM, 0, "", (host, port))]


class HTTPResult:
    """
    A parsed HTTP response.

    ``headers`` maps lowercase header names to lists of values, so repeated headers such as
    ``Set-Cookie`` are kept. ``body`` is the raw bytes after the blank line. Chunked bodies
    are not decoded.
    """

    def __init__(self, raw: bytes):
        head, _, self.body = raw.partition(b"\r\n\r\n")
        lines = head.decode("utf-8").split("\r\n")

        self.status_line = lines[0]
        self.http_version, code, self.reason = lines[0].split(" ", 2)
        self.status = int(code)

        self.headers = {}
        for line in lines[1:]:
            name, value = line.split(": ", 1)
            self.headers.setdefault(name.lower(), []).append(value)

    def header(self, name):
        """First value of header ``name`` (case-insensitive), or ``None``."""
        values = self.headers.get(name.lower())
        return values[0] if values else None

    def __repr__(self):
        return f"<HTTPResult {self.status_line!r} {self.headers!r} {self.body!r}>"


def _read_until_closed(sock: socket.socket) -> bytes:
    received = b""
    while chunk := sock.recv(4096):
        received += chunk
    return received


def server_port(server: Server) -> int:
    """The port the OS assigned to a server started on port 0."""
    return server._sock.getsockname()[1]


@pytest.fixture(autouse=True)
def _restore_mime_types():
    """``MIMETypes`` keeps its configuration in class attributes. Undo changes after each test."""
    default = MIMETypes.DEFAULT
    registered = dict(MIMETypes.REGISTERED)
    yield
    MIMETypes.DEFAULT = default
    MIMETypes.REGISTERED = registered


@pytest.fixture
def fake_socket():
    """The ``FakeSocket`` class."""
    return FakeSocket


@pytest.fixture
def fake_pool():
    """The ``FakePool`` class."""
    return FakePool


@pytest.fixture
def parse_response():
    """Function that parses raw response bytes into an ``HTTPResult``."""
    return HTTPResult


@pytest.fixture
def make_request():
    """
    Factory that builds a ``Request`` from raw bytes without any networking.

    The request's connection is a ``FakeSocket`` unless ``conn`` is given, and its server is
    an unstarted ``Server`` on a ``FakePool`` unless ``server`` is given.
    """

    def factory(raw: bytes, *, conn=None, server=None, client_address=CLIENT_ADDRESS):
        if server is None:
            server = Server(FakePool())
        if conn is None:
            conn = FakeSocket()
        return Request(server, conn, client_address, raw)

    return factory


@pytest.fixture
def make_server():
    """
    Factory for real-socket ``Server`` instances.

    Takes the same arguments as ``Server`` except ``socket_source``. Unless ``start=False``,
    the server is started on 127.0.0.1 with an OS-assigned port. Servers still running at
    the end of the test are stopped.
    """
    servers = []

    def factory(root_path=None, *, start=True, **kwargs):
        server = Server(socket, root_path, **kwargs)
        servers.append(server)
        if start:
            server.start("127.0.0.1", 0)
        return server

    yield factory

    for server in servers:
        if not server.stopped:
            server.stop()


@pytest.fixture
def http():
    """
    Function ``http(server, raw, *, shutdown=False)`` that sends ``raw`` to a running
    real-socket server, calls ``server.poll()`` once, and reads the reply until the server
    closes the connection.

    Returns ``(poll_result, HTTPResult or None)``, with ``None`` if the server sent nothing.
    ``shutdown=True`` half-closes the client after sending, so the server sees end of input.
    Exceptions raised by ``poll()`` propagate.
    """

    def send(server: Server, raw: bytes, *, shutdown: bool = False):
        with socket.create_connection(("127.0.0.1", server_port(server)), timeout=5) as client:
            if raw:
                client.sendall(raw)
            if shutdown:
                client.shutdown(socket.SHUT_WR)
            poll_result = server.poll()
            reply = _read_until_closed(client)
        return poll_result, (HTTPResult(reply) if reply else None)

    return send


@pytest.fixture
def port_of():
    """Function returning the OS-assigned port of a real-socket server."""
    return server_port


@pytest.fixture
def tls_cert(tmp_path):
    """
    ``(certfile, keyfile)`` paths for a throwaway self-signed certificate for localhost.

    Generated with the ``openssl`` command, since CPython's ``ssl`` module cannot create
    certificates. Skips the test if ``openssl`` is not installed.
    """
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl command not found")

    certfile = tmp_path / "cert.pem"
    keyfile = tmp_path / "key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:prime256v1",
            "-nodes",
            "-subj",
            "/CN=localhost",
            "-days",
            "1",
            "-keyout",
            str(keyfile),
            "-out",
            str(certfile),
        ],
        check=True,
        capture_output=True,
    )
    return str(certfile), str(keyfile)
