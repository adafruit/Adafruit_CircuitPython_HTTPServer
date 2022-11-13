try:
    from typing import Dict, Tuple
except ImportError:
    pass


class HTTPRequest:

    method: str
    path: str
    query_params: Dict[str, str]
    http_version: str

    headers: Dict[str, str]
    body: bytes | None

    raw_request: bytes

    def __init__(
        self, raw_request: bytes = None
    ) -> None:
        self.raw_request = raw_request

        if raw_request is None: raise ValueError("raw_request cannot be None")

        empty_line_index = raw_request.find(b"\r\n\r\n")

        header_bytes = raw_request[:empty_line_index]
        body_bytes = raw_request[empty_line_index + 4:]

        try:
            self.method, self.path, self.query_params, self.http_version = self._parse_start_line(header_bytes)
            self.headers = self._parse_headers(header_bytes)
            self.body = body_bytes
        except Exception as error:
            raise ValueError("Unparseable raw_request: ", raw_request) from error


    @staticmethod
    def _parse_start_line(header_bytes: bytes) -> Tuple[str, str, Dict[str, str], str]:
        """Parse HTTP Start line to method, path, query_params and http_version."""

        start_line = header_bytes.decode("utf8").splitlines()[0]

        method, path, http_version = start_line.split()

        if "?" not in path: path += "?"

        path, query_string = path.split("?", 1)
        query_params = dict([param.split("=", 1) for param in query_string.split("&")]) if query_string else {}

        return method, path, query_params, http_version


    @staticmethod
    def _parse_headers(header_bytes: bytes) -> Dict[str, str]:
        """Parse HTTP headers from raw request."""
        header_lines = header_bytes.decode("utf8").splitlines()[1:]

        return dict([header.split(": ", 1) for header in header_lines[1:]])
