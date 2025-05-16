# SPDX-FileCopyrightText: Copyright (c) 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: MIT
"""
`adafruit_httpserver`
================================================================================

Socket based HTTP Server for CircuitPython


* Author(s): Dan Halbert, Michał Pokusa

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_HTTPServer.git"


from .authentication import (
    Basic,
    Bearer,
    Token,
    check_authentication,
    require_authentication,
)
from .exceptions import (
    AuthenticationError,
    BackslashInPathError,
    FileNotExistsError,
    InvalidPathError,
    ParentDirectoryReferenceError,
    ServerStoppedError,
    ServingFilesDisabledError,
)
from .headers import Headers
from .methods import (
    CONNECT,
    DELETE,
    GET,
    HEAD,
    OPTIONS,
    PATCH,
    POST,
    PUT,
    TRACE,
)
from .mime_types import MIMETypes
from .request import FormData, QueryParams, Request
from .response import (
    ChunkedResponse,
    FileResponse,
    JSONResponse,
    Redirect,
    Response,
    SSEResponse,
    Websocket,
)
from .route import Route, as_route
from .server import (
    CONNECTION_TIMED_OUT,
    NO_REQUEST,
    REQUEST_HANDLED_NO_RESPONSE,
    REQUEST_HANDLED_RESPONSE_SENT,
    Server,
)
from .status import (
    ACCEPTED_202,
    BAD_REQUEST_400,
    CREATED_201,
    FORBIDDEN_403,
    FOUND_302,
    INTERNAL_SERVER_ERROR_500,
    METHOD_NOT_ALLOWED_405,
    MOVED_PERMANENTLY_301,
    NO_CONTENT_204,
    NOT_FOUND_404,
    NOT_IMPLEMENTED_501,
    OK_200,
    PARTIAL_CONTENT_206,
    PERMANENT_REDIRECT_308,
    SERVICE_UNAVAILABLE_503,
    SWITCHING_PROTOCOLS_101,
    TEMPORARY_REDIRECT_307,
    TOO_MANY_REQUESTS_429,
    UNAUTHORIZED_401,
    Status,
)
