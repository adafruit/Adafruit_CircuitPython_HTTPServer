class HTTPStatus:  # pylint: disable=too-few-public-methods
    """HTTP status codes."""

    def __init__(self, code, text):
        """Define a status code.

        :param int value: Numeric value: 200, 404, etc.
        :param str phrase: Short phrase: "OK", "Not Found', etc.
        """
        self.code = code
        self.text = text

    def __repr__(self):
        return f'HTTPStatus({self.code}, "{self.text}")'

    def __str__(self):
        return f"{self.code} {self.text}"


OK_200 = HTTPStatus(200, "OK")
BAD_REQUEST_400 = HTTPStatus(400, "Bad Request")
NOT_FOUND_404 = HTTPStatus(404, "Not Found")
INTERNAL_SERVER_ERROR_500 = HTTPStatus(500, "Internal Server Error")
