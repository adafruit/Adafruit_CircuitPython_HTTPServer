# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries, Michał Pokusa
#
# SPDX-License-Identifier: Unlicense


import socketpool
import wifi

from adafruit_httpserver import Server, Request, FileResponse


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=True)


@server.route("/home")
def home(request: Request):
    """
    Serves the file /www/home.html.
    """

    return FileResponse(request, "home.html", "/www")


server.serve_forever(str(wifi.radio.ipv4_address))
