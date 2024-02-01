# SPDX-FileCopyrightText: 2024 Michał Pokusa
#
# SPDX-License-Identifier: Unlicense

import socket

from adafruit_httpserver import Server, Request, Response


pool = socket
server = Server(pool, "/static", debug=True)


@server.route("/")
def base(request: Request):
    """
    Serve a default static plain text message.
    """
    return Response(request, "Hello from the CircuitPython HTTP Server!")


# runs on port 5000; ports < 1024 require sudo.
server.serve_forever("0.0.0.0", 5000)
