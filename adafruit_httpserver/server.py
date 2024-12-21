# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver.server`
====================================================
* Author(s): Dan Halbert, Michał Pokusa
"""

try:
    from typing import Callable, Union, List, Tuple, Dict, Iterable
except ImportError:
    pass

from ssl import SSLContext, create_default_context
from errno import EAGAIN, ECONNRESET, ETIMEDOUT
from sys import implementation
from time import monotonic, sleep
from traceback import print_exception

from .authentication import Basic, Token, Bearer, require_authentication
from .exceptions import (
    ServerStoppedError,
    AuthenticationError,
    FileNotExistsError,
    InvalidPathError,
    ServingFilesDisabledError,
)
from .headers import Headers
from .interfaces import _ISocketPool, _ISocket
from .methods import GET, HEAD
from .request import Request
from .response import Response, FileResponse
from .route import Route
from .status import BAD_REQUEST_400, UNAUTHORIZED_401, FORBIDDEN_403, NOT_FOUND_404

if implementation.name != "circuitpython":
    from ssl import Purpose, CERT_NONE, SSLError  # pylint: disable=ungrouped-imports


NO_REQUEST = "no_request"
CONNECTION_TIMED_OUT = "connection_timed_out"
REQUEST_HANDLED_NO_RESPONSE = "request_handled_no_response"
REQUEST_HANDLED_RESPONSE_SENT = "request_handled_response_sent"

# CircuitPython does not have these error codes
MBEDTLS_ERR_SSL_FATAL_ALERT_MESSAGE = -30592


class Server:  # pylint: disable=too-many-instance-attributes
    """A basic socket-based HTTP server."""

    host: str
    """Host name or IP address the server is listening on. ``None`` if server is stopped."""

    port: int
    """Port the server is listening on. ``None`` if server is stopped."""

    root_path: str
    """Root directory to serve files from. ``None`` if serving files is disabled."""

    @staticmethod
    def _validate_https_cert_provided(
        certfile: Union[str, None], keyfile: Union[str, None]
    ) -> None:
        if certfile is None or keyfile is None:
            raise ValueError("Both certfile and keyfile must be specified for HTTPS")

    @staticmethod
    def _create_circuitpython_ssl_context(certfile: str, keyfile: str) -> SSLContext:
        ssl_context = create_default_context()

        ssl_context.load_verify_locations(cadata="")
        ssl_context.load_cert_chain(certfile, keyfile)

        return ssl_context

    @staticmethod
    def _create_cpython_ssl_context(certfile: str, keyfile: str) -> SSLContext:
        ssl_context = create_default_context(purpose=Purpose.CLIENT_AUTH)

        ssl_context.load_cert_chain(certfile, keyfile)

        ssl_context.verify_mode = CERT_NONE
        ssl_context.check_hostname = False

        return ssl_context

    @classmethod
    def _create_ssl_context(cls, certfile: str, keyfile: str) -> SSLContext:
        return (
            cls._create_circuitpython_ssl_context(certfile, keyfile)
            if implementation.name == "circuitpython"
            else cls._create_cpython_ssl_context(certfile, keyfile)
        )

    def __init__(
        self,
        socket_source: _ISocketPool,
        root_path: str = None,
        *,
        https: bool = False,
        certfile: str = None,
        keyfile: str = None,
        debug: bool = False,
    ) -> None:
        """Create a server, and get it ready to run.

        :param socket: An object that is a source of sockets. This could be a `socketpool`
          in CircuitPython or the `socket` module in CPython.
        :param str root_path: Root directory to serve files from
        :param bool debug: Enables debug messages useful during development
        :param bool https: If True, the server will use HTTPS
        :param str certfile: Path to the certificate file, required if ``https`` is True
        :param str keyfile: Path to the private key file, required if ``https`` is True
        """
        self._buffer = bytearray(1024)
        self._timeout = 1

        self._auths = []
        self._routes: "List[Route]" = []
        self.headers = Headers()

        self._socket_source = socket_source
        self._sock = None

        self.host, self.port = None, None
        self.root_path = root_path
        self.https = https

        if https:
            self._validate_https_cert_provided(certfile, keyfile)
            self._ssl_context = self._create_ssl_context(certfile, keyfile)
        else:
            self._ssl_context = None

        if root_path in ["", "/"] and debug:
            _debug_warning_exposed_files(root_path)
        self.stopped = True

        self.debug = debug

    def route(
        self,
        path: str,
        methods: Union[str, Iterable[str]] = GET,
        *,
        append_slash: bool = False,
    ) -> Callable:
        """
        Decorator used to add a route.

        If request matches multiple routes, the first matched one added will be used.

        :param str path: URL path
        :param str methods: HTTP method(s): ``"GET"``, ``"POST"``, ``["GET", "POST"]`` etc.
        :param bool append_slash: If True, the route will be accessible with and without a
          trailing slash

        Example::

            # Default method is GET
            @server.route("/example")
            def route_func(request):
                ...

            # It is necessary to specify other methods like POST, PUT, etc.
            @server.route("/example", POST)
            def route_func(request):
                ...

            # If you want to access URL with and without trailing slash, use append_slash=True
            @server.route("/example-with-slash", append_slash=True)
            # which is equivalent to
            @server.route("/example-with-slash")
            @server.route("/example-with-slash/")
            def route_func(request):
                ...

            # Multiple methods can be specified
            @server.route("/example", [GET, POST])
            def route_func(request):
                ...

            # URL parameters can be specified
            @server.route("/example/<my_parameter>", GET) e.g. /example/123
            def route_func(request, my_parameter):
                ...

            # It is possible to use wildcard that can match any number of path segments
            @server.route("/example/.../something", GET) # e.g. /example/123/something
            @server.route("/example/..../something", GET) # e.g. /example/123/456/something
            def route_func(request):
                ...
        """

        def route_decorator(func: Callable) -> Callable:
            self._routes.append(Route(path, methods, func, append_slash=append_slash))
            return func

        return route_decorator

    def add_routes(self, routes: List[Route]) -> None:
        """
        Add multiple routes at once.

        :param List[Route] routes: List of routes to add to the server

        Example::

            from separate_file import external_route1, external_route2

            ...

            server.add_routes([
                Route("/example", GET, route_func1, append_slash=True),
                Route("/example/<my_parameter>", GET, route_func2),
                Route("/example/..../something", [GET, POST], route_func3),
                external_route1,
                external_route2,
            ]}
        """
        self._routes.extend(routes)

    def _verify_can_start(self, host: str, port: int) -> None:
        """Check if the server can be successfully started. Raises RuntimeError if not."""

        if host is None or port is None:
            raise RuntimeError("Host and port cannot be None")

        try:
            self._socket_source.getaddrinfo(host, port)
        except OSError as error:
            raise RuntimeError(f"Cannot start server on {host}:{port}") from error

    def serve_forever(
        self, host: str = "0.0.0.0", port: int = 5000, *, poll_interval: float = 0.1
    ) -> None:
        """
        Wait for HTTP requests at the given host and port. Does not return.
        Ignores any exceptions raised by the handler function and continues to serve.
        Returns only when the server is stopped by calling ``.stop()``.

        :param str host: host name or IP address
        :param int port: port
        :param float poll_interval: interval between polls in seconds
        """
        self.start(host, port)

        while not self.stopped:
            try:
                if self.poll() == NO_REQUEST and poll_interval is not None:
                    sleep(poll_interval)
            except KeyboardInterrupt:  # Exit on Ctrl-C e.g. during development
                self.stop()
                return
            except Exception:  # pylint: disable=broad-except
                pass  # Ignore exceptions in handler function

    @staticmethod
    def _create_server_socket(
        socket_source: _ISocketPool,
        ssl_context: "SSLContext | None",
        host: str,
        port: int,
    ) -> _ISocket:
        sock = socket_source.socket(socket_source.AF_INET, socket_source.SOCK_STREAM)

        # TODO: Temporary backwards compatibility, remove after CircuitPython 9.0.0 release
        if implementation.version >= (9,) or implementation.name != "circuitpython":
            sock.setsockopt(socket_source.SOL_SOCKET, socket_source.SO_REUSEADDR, 1)

        if ssl_context is not None:
            sock = ssl_context.wrap_socket(sock, server_side=True)

        sock.bind((host, port))
        sock.listen(10)
        sock.setblocking(False)  # Non-blocking socket

        return sock

    def start(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        """
        Start the HTTP server at the given host and port. Requires calling
        ``.poll()`` in a while loop to handle incoming requests.

        :param str host: host name or IP address
        :param int port: port
        """
        self._verify_can_start(host, port)

        self.host, self.port = host, port

        self.stopped = False
        self._sock = self._create_server_socket(
            self._socket_source, self._ssl_context, host, port
        )

        if self.debug:
            _debug_started_server(self)

    def stop(self) -> None:
        """
        Stops the server from listening for new connections and closes the socket.
        Current requests will be processed. Server can be started again by calling ``.start()``
        or ``.serve_forever()``.
        """
        self.host, self.port = None, None

        self.stopped = True
        self._sock.close()

        if self.debug:
            _debug_stopped_server(self)

    def _receive_header_bytes(self, sock: _ISocket) -> bytes:
        """Receive bytes until a empty line is received."""
        received_bytes = bytes()
        while b"\r\n\r\n" not in received_bytes:
            try:
                length = sock.recv_into(self._buffer, len(self._buffer))
                received_bytes += self._buffer[:length]
            except OSError as ex:
                if ex.errno == ETIMEDOUT:
                    break
                raise
            except Exception as ex:
                raise ex
        return received_bytes

    def _receive_body_bytes(
        self,
        sock: _ISocket,
        received_body_bytes: bytes,
        content_length: int,
    ) -> bytes:
        """Receive bytes until the given content length is received."""
        while len(received_body_bytes) < content_length:
            try:
                length = sock.recv_into(self._buffer, len(self._buffer))
                received_body_bytes += self._buffer[:length]
            except OSError as ex:
                if ex.errno == ETIMEDOUT:
                    break
                raise
            except Exception as ex:
                raise ex
        return received_body_bytes[:content_length]

    def _receive_request(
        self,
        sock: _ISocket,
        client_address: Tuple[str, int],
    ) -> Request:
        """Receive bytes from socket until the whole request is received."""

        # Receiving data until empty line
        header_bytes = self._receive_header_bytes(sock)

        # Return if no data received
        if not header_bytes:
            return None

        request = Request(self, sock, client_address, header_bytes)

        content_length = int(request.headers.get_directive("Content-Length", 0))
        received_body_bytes = request.body

        # Receiving remaining body bytes
        request.body = self._receive_body_bytes(
            sock, received_body_bytes, content_length
        )

        return request

    def _find_handler(  # pylint: disable=cell-var-from-loop
        self, method: str, path: str
    ) -> Union[Callable[..., "Response"], None]:
        """
        Finds a handler for a given route.

        If route used URL parameters, the handler will be wrapped to pass the parameters to the
        handler.

        Example::

            @server.route("/example/<my_parameter>", GET)
            def route_func(request, my_parameter):
                ...
                request.path == "/example/123" # True
                my_parameter == "123" # True
        """
        for route in self._routes:
            route_matches, url_parameters = route.matches(method, path)

            if route_matches:

                def wrapped_handler(request):
                    return route.handler(request, **url_parameters)

                return wrapped_handler

        return None

    def _handle_request(
        self, request: Request, handler: Union[Callable, None]
    ) -> Union[Response, None]:
        try:
            # Check server authentications if necessary
            if self._auths:
                require_authentication(request, self._auths)

            # Handler for route exists and is callable
            if handler is not None and callable(handler):
                return handler(request)

            # No root_path, access to filesystem disabled, return 404.
            if self.root_path is None:
                raise ServingFilesDisabledError

            # Method is GET or HEAD, try to serve a file from the filesystem.
            if request.method in (GET, HEAD):
                return FileResponse(
                    request,
                    filename=request.path,
                    head_only=request.method == HEAD,
                )

            return Response(request, status=BAD_REQUEST_400)

        except AuthenticationError:
            return Response(
                request,
                status=UNAUTHORIZED_401,
                headers={"WWW-Authenticate": 'Basic charset="UTF-8"'},
            )

        except InvalidPathError as error:
            return Response(
                request,
                str(error) if self.debug else "Invalid path",
                status=FORBIDDEN_403,
            )

        except (FileNotExistsError, ServingFilesDisabledError) as error:
            return Response(
                request,
                str(error) if self.debug else "File not found",
                status=NOT_FOUND_404,
            )

    def _set_default_server_headers(self, response: Response) -> None:
        for name, value in self.headers.items():
            response._headers.setdefault(  # pylint: disable=protected-access
                name, value
            )

    def poll(  # pylint: disable=too-many-branches,too-many-return-statements
        self,
    ) -> str:
        """
        Call this method inside your main loop to get the server to check for new incoming client
        requests. When a request comes in, it will be handled by the handler function.

        Returns str representing the result of the poll
        e.g. ``NO_REQUEST`` or ``REQUEST_HANDLED_RESPONSE_SENT``.
        """
        if self.stopped:
            raise ServerStoppedError

        conn = None
        try:
            if self.debug:
                _debug_start_time = monotonic()

            conn, client_address = self._sock.accept()
            conn.settimeout(self._timeout)

            # Receive the whole request
            if (request := self._receive_request(conn, client_address)) is None:
                conn.close()
                return CONNECTION_TIMED_OUT

            # Find a route that matches the request's method and path and get its handler
            handler = self._find_handler(request.method, request.path)

            # Handle the request
            response = self._handle_request(request, handler)

            if response is None:
                conn.close()
                return REQUEST_HANDLED_NO_RESPONSE

            self._set_default_server_headers(response)

            # Send the response
            response._send()  # pylint: disable=protected-access

            if self.debug:
                _debug_end_time = monotonic()
                _debug_response_sent(response, _debug_end_time - _debug_start_time)

            return REQUEST_HANDLED_RESPONSE_SENT

        except Exception as error:  # pylint: disable=broad-except
            if isinstance(error, OSError):
                # There is no data available right now, try again later.
                if error.errno == EAGAIN:
                    return NO_REQUEST
                # Connection reset by peer, try again later.
                if error.errno == ECONNRESET:
                    return NO_REQUEST
                # Handshake failed, try again later.
                if error.errno == MBEDTLS_ERR_SSL_FATAL_ALERT_MESSAGE:
                    return NO_REQUEST

            # CPython specific SSL related errors
            if implementation.name != "circuitpython" and isinstance(error, SSLError):
                # Ignore unknown SSL certificate errors
                if getattr(error, "reason", None) == "SSLV3_ALERT_CERTIFICATE_UNKNOWN":
                    return NO_REQUEST

            if self.debug:
                _debug_exception_in_handler(error)

            if conn is not None:
                conn.close()
            raise error  # Raise the exception again to be handled by the user.

    def require_authentication(self, auths: List[Union[Basic, Token, Bearer]]) -> None:
        """
        Requires authentication for all routes and files in ``root_path``.
        Any non-authenticated request will be rejected with a 401 status code.

        Example::

            server = Server(pool, "/static")
            server.require_authentication([Basic("username", "password")])
        """
        self._auths = auths

    @property
    def headers(self) -> Headers:
        """
        Headers to be sent with every response, without the need to specify them in each handler.

        If a header is specified in both the handler and the server, the handler's header will be
        used.

        Example::

            server = Server(pool, "/static")
            server.headers = {
                "X-Server": "Adafruit CircuitPython HTTP Server",
                "Access-Control-Allow-Origin": "*",
            }
        """
        return self._headers

    @headers.setter
    def headers(self, value: Union[Headers, Dict[str, str]]) -> None:
        self._headers = value.copy() if isinstance(value, Headers) else Headers(value)

    @property
    def request_buffer_size(self) -> int:
        """
        The maximum size of the incoming request buffer. If the default size isn't
        adequate to handle your incoming data you can set this after creating the
        server instance.

        Default size is 1024 bytes.

        Example::

            server = Server(pool, "/static")
            server.request_buffer_size = 2048

            server.serve_forever(str(wifi.radio.ipv4_address))
        """
        return len(self._buffer)

    @request_buffer_size.setter
    def request_buffer_size(self, value: int) -> None:
        self._buffer = bytearray(value)

    @property
    def socket_timeout(self) -> int:
        """
        Timeout after which the socket will stop waiting for more incoming data.

        Must be set to positive integer or float. Default is 1 second.

        When exceeded, raises `OSError` with `errno.ETIMEDOUT`.

        Example::

            server = Server(pool, "/static")
            server.socket_timeout = 3

            server.serve_forever(str(wifi.radio.ipv4_address))
        """
        return self._timeout

    @socket_timeout.setter
    def socket_timeout(self, value: int) -> None:
        if isinstance(value, (int, float)) and value > 0:
            self._timeout = value
        else:
            raise ValueError("Server.socket_timeout must be a positive numeric value.")

    def __repr__(self) -> str:
        host = self.host
        port = self.port
        root_path = self.root_path

        return f"<Server {host=}, {port=}, {root_path=}>"


def _debug_warning_exposed_files(root_path: str):
    """Warns about exposing all files on the device."""
    print(
        f"WARNING: Setting root_path to '{root_path}' will expose all files on your device through"
        " the webserver, including potentially sensitive files like settings.toml or secrets.py. "
        "Consider making a sub-directory on your device and using that for your root_path instead."
    )


def _debug_started_server(server: "Server"):
    """Prints a message when the server starts."""
    scheme = "https" if server.https else "http"
    host, port = server.host, server.port

    print(f"Started development server on {scheme}://{host}:{port}")


def _debug_response_sent(response: "Response", time_elapsed: float):
    """Prints a message after a response is sent."""
    # pylint: disable=protected-access
    client_ip = response._request.client_address[0]
    method = response._request.method
    query_params = response._request.query_params
    path = response._request.path + (f"?{query_params}" if query_params else "")
    req_size = len(response._request.raw_request)
    status = response._status
    res_size = response._size
    time_elapsed_ms = f"{round(time_elapsed*1000)}ms"

    print(
        f'{client_ip} -- "{method} {path}" {req_size} -- "{status}" {res_size} -- {time_elapsed_ms}'
    )


def _debug_stopped_server(server: "Server"):  # pylint: disable=unused-argument
    """Prints a message after the server stops."""
    print("Stopped development server")


def _debug_exception_in_handler(error: Exception):
    """Prints a message when an exception is raised in a handler."""
    print_exception(error)
