# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense


import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static")


@server.route("/home")
def home(request: Request):
    """
    Serves the file /www/home.html.
    """

    with Response(request, content_type="text/html") as response:
        response.send_file("home.html", root_path="/www")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))