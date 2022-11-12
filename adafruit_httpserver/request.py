from typing import Dict, Tuple


class HTTPRequest:

    method: str
    path: str
    query_params: Dict[str, str] = {}
    http_version: str

    headers: Dict[str, str] = {}
    body: bytes | None

    raw_request: bytes

    def __init__(
        self, raw_request: bytes = None
    ) -> None:
        self.raw_request = raw_request

        if raw_request is None: raise ValueError("raw_request cannot be None")

        try:
            self.method, self.path, self.query_params, self.http_version = self.parse_start_line(raw_request)
            self.headers = self.parse_headers(raw_request)
            self.body = self.parse_body(raw_request)
        except Exception as error:
            raise ValueError("Unparseable raw_request: ", raw_request) from error


    @staticmethod
    def parse_start_line(raw_request: bytes) -> Tuple(str, str, Dict[str, str], str):
        """Parse HTTP Start line to method, path, query_params and http_version."""

        start_line = raw_request.decode("utf8").splitlines()[0]

        method, path, http_version = start_line.split()

        if "?" not in path: path += "?"

        path, query_string = path.split("?", 1)
        query_params = dict([param.split("=", 1) for param in query_string.split("&")]) if query_string else {}

        return method, path, query_params, http_version


    @staticmethod
    def parse_headers(raw_request: bytes) -> Dict[str, str]:
        """Parse HTTP headers from raw request."""
        parsed_request_lines = raw_request.decode("utf8").splitlines()
        empty_line = parsed_request_lines.index("")

        return dict([header.split(": ", 1) for header in parsed_request_lines[1:empty_line]])


    @staticmethod
    def parse_body(raw_request: bytes) -> Dict[str, str]:
        """Parse HTTP body from raw request."""
        parsed_request_lines = raw_request.decode("utf8").splitlines()
        empty_line = parsed_request_lines.index("")

        if empty_line == len(parsed_request_lines) - 1:
            return None
        return "\r\n".join(parsed_request_lines[empty_line+1:])
