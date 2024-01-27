# SPDX-FileCopyrightText: 2024 Ted Timmons
#
# SPDX-License-Identifier: Unlicense
#
# Simple example showing how to use httpserver in cpython (e.g., on a computer).

import socket
from adafruit_httpserver import Server, Request, Response


# fake the wifi class, reduces changes required later in the code.
class wifi:  # pylint: disable=too-few-public-methods
    class radio:  # pylint: disable=too-few-public-methods
        ipv4_address = "0.0.0.0"


pool = socket
server = Server(pool, "/static", debug=True)


@server.route("/")
def base(request: Request):
    """
    Serve a default static plain text message.
    """
    return Response(request, "Hello from the CircuitPython HTTP Server!")


server.serve_forever(str(wifi.radio.ipv4_address))
