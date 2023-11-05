# SPDX-FileCopyrightText: 2023 Michal Pokusa
#
# SPDX-License-Identifier: Unlicense
import os
import re

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, FileResponse

try:
    from adafruit_templateengine import render_template
except ImportError as e:
    raise ImportError("This example requires adafruit_templateengine library.") from e


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=True)

# Create /static directory if it doesn't exist
try:
    os.listdir("/static")
except OSError as e:
    raise OSError("Please create a /static directory on the CIRCUITPY drive.") from e


@server.route("/")
def directory_listing(request: Request):
    path = request.query_params.get("path", "").replace("%20", " ")

    # Preventing path traversal by removing all ../ from path
    path = re.sub(r"\/(\.\.)\/|\/(\.\.)|(\.\.)\/", "/", path).strip("/")

    if path:
        is_file = (
            os.stat(f"/static/{path}")[0] & 0b_11110000_00000000
        ) == 0b_10000000_00000000
    else:
        is_file = False

    # If path is a file, return it as a file response
    if is_file:
        return FileResponse(request, path)

    # Otherwise, return a directory listing
    return Response(
        request,
        render_template(
            "directory_listing.tpl.html",
            context={
                "path": path,
                "items": os.listdir(f"/static/{path}"),
            },
        ),
        content_type="text/html",
    )


# Start the server.
server.serve_forever(str(wifi.radio.ipv4_address))
