class HTTPStatus:  # pylint: disable=too-few-public-methods
    """HTTP status codes."""

    def __init__(self, value, phrase):
        """Define a status code.

        :param int value: Numeric value: 200, 404, etc.
        :param str phrase: Short phrase: "OK", "Not Found', etc.
        """
        self.value = value
        self.phrase = phrase

    def __repr__(self):
        return f'HTTPStatus({self.value}, "{self.phrase}")'

    def __str__(self):
        return f"{self.value} {self.phrase}"


HTTPStatus.NOT_FOUND = HTTPStatus(404, "Not Found")
"""404 Not Found"""
HTTPStatus.OK = HTTPStatus(200, "OK")  # pylint: disable=invalid-name
"""200 OK"""
HTTPStatus.INTERNAL_SERVER_ERROR = HTTPStatus(500, "Internal Server Error")
"""500 Internal Server Error"""
