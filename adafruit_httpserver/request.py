
class _HTTPRequest:
    def __init__(
        self, path: str = "", method: str = "", raw_request: bytes = None
    ) -> None:
        self.raw_request = raw_request
        if raw_request is None:
            self.path = path
            self.method = method
        else:
            # Parse request data from raw request
            request_text = raw_request.decode("utf8")
            first_line = request_text[: request_text.find("\n")]
            try:
                (self.method, self.path, _httpversion) = first_line.split()
            except ValueError as exc:
                raise ValueError("Unparseable raw_request: ", raw_request) from exc

    def __hash__(self) -> int:
        return hash(self.method) ^ hash(self.path)

    def __eq__(self, other: "_HTTPRequest") -> bool:
        return self.method == other.method and self.path == other.path

    def __repr__(self) -> str:
        return f"_HTTPRequest(path={repr(self.path)}, method={repr(self.method)})"
