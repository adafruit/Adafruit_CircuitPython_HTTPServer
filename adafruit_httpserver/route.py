from .methods import HTTPMethod


class HTTPRoute:
    def __init__(
        self,
        path: str = "",
        method: HTTPMethod = HTTPMethod.GET
    ) -> None:

        self.path = path
        self.method = method

    def __hash__(self) -> int:
        return hash(self.method) ^ hash(self.path)

    def __eq__(self, other: "HTTPRoute") -> bool:
        return self.method == other.method and self.path == other.path

    def __repr__(self) -> str:
        return f"HTTPRoute(path={repr(self.path)}, method={repr(self.method)})"
