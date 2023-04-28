# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static")


@server.route("/")
def base(request: Request):
    """
    Serve the default index.html file.
    """
    with Response(request, content_type="text/html") as response:
        response.send_file("index.html")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")

# Start the server.
server.start(str(wifi.radio.ipv4_address))

while True:
    try:
        # Do something useful in this section,
        # for example read a sensor and capture an average,
        # or a running total of the last 10 samples

        # Process any waiting requests
        server.poll()
    except OSError as error:
        print(error)
        continue
