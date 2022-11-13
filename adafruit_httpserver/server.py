try:
    from typing import Any, Callable
except ImportError:
    pass

from errno import EAGAIN, ECONNRESET

from .methods import HTTPMethod
from .request import HTTPRequest
from .response import HTTPResponse
from .route import HTTPRoute
from .status import BAD_REQUEST_400

class HTTPServer:
    """A basic socket-based HTTP server."""

    def __init__(self, socket_source: Any) -> None:
        # TODO: Use a Protocol for the type annotation.
        # The Protocol could be refactored from adafruit_requests.
        """Create a server, and get it ready to run.

        :param socket: An object that is a source of sockets. This could be a `socketpool`
          in CircuitPython or the `socket` module in CPython.
        """
        self._buffer = bytearray(1024)
        self.route_handlers = {}
        self._socket_source = socket_source
        self._sock = None
        self.root_path = "/"

    def route(self, path: str, method: HTTPMethod = HTTPMethod.GET):
        """Decorator used to add a route.

        :param str path: filename path
        :param HTTPMethod method: HTTP method: HTTPMethod.GET, HTTPMethod.POST, etc.

        Example::

            @server.route(path, method)
            def route_func(request):
                raw_text = request.raw_request.decode("utf8")
                print("Received a request of length", len(raw_text), "bytes")
                return HTTPResponse(body="hello world")

        """

        def route_decorator(func: Callable) -> Callable:
            self.route_handlers[HTTPRoute(path, method)] = func
            return func

        return route_decorator

    def serve_forever(self, host: str, port: int = 80, root_path: str = "") -> None:
        """Wait for HTTP requests at the given host and port. Does not return.

        :param str host: host name or IP address
        :param int port: port
        :param str root: root directory to serve files from
        """
        self.start(host, port, root_path)

        while True:
            try:
                self.poll()
            except OSError:
                continue

    def start(self, host: str, port: int = 80, root_path: str = "") -> None:
        """
        Start the HTTP server at the given host and port. Requires calling
        poll() in a while loop to handle incoming requests.

        :param str host: host name or IP address
        :param int port: port
        :param str root: root directory to serve files from
        """
        self.root_path = root_path

        self._sock = self._socket_source.socket(
            self._socket_source.AF_INET, self._socket_source.SOCK_STREAM
        )
        self._sock.bind((host, port))
        self._sock.listen(10)
        self._sock.setblocking(False)  # non-blocking socket

    def poll(self):
        """
        Call this method inside your main event loop to get the server to
        check for new incoming client requests. When a request comes in,
        the application callable will be invoked.
        """
        try:
            conn, _ = self._sock.accept()
            with conn:
                conn.setblocking(True)
                length, _ = conn.recvfrom_into(self._buffer)

                request = HTTPRequest(raw_request=self._buffer[:length])

                handler = self.route_handlers.get(HTTPRoute(request.path, request.method), None)

                # If a handler for route exists, call it.
                if handler:
                    response = handler(request)

                # If no handler exists and request method is GET, try to serve a file.
                elif request.method == HTTPMethod.GET:
                    response = HTTPResponse(filename=request.path, root_path=self.root_path)

                # If no handler exists and request method is not GET, return 400 Bad Request.
                else:
                    response = HTTPResponse(status=BAD_REQUEST_400)

                response.send(conn)
        except OSError as ex:
            # handle EAGAIN and ECONNRESET
            if ex.errno == EAGAIN:
                # there is no data available right now, try again later.
                return
            if ex.errno == ECONNRESET:
                # connection reset by peer, try again later.
                return
            raise

    @property
    def request_buffer_size(self) -> int:
        """
        The maximum size of the incoming request buffer. If the default size isn't
        adequate to handle your incoming data you can set this after creating the
        server instance.

        Default size is 1024 bytes.

        Example::

            server = HTTPServer(pool)
            server.request_buffer_size = 2048

            server.serve_forever(str(wifi.radio.ipv4_address))
        """
        return len(self._buffer)

    @request_buffer_size.setter
    def request_buffer_size(self, value: int) -> None:
        self._buffer = bytearray(value)
