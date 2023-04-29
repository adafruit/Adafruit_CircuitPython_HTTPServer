# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response


pool = socketpool.SocketPool(wifi.radio)

bedroom_server = Server(pool, "/bedroom")
office_server = Server(pool, "/office")


@bedroom_server.route("/bedroom")
def bedroom(request: Request):
    """
    This route is registered only with ``bedroom_server``.
    """
    with Response(request) as response:
        response.send("Hello from the bedroom!")


@office_server.route("/office")
def office(request: Request):
    """
    This route is registered only with ``office_server``.
    """
    with Response(request) as response:
        response.send("Hello from the office!")


@bedroom_server.route("/home")
@office_server.route("/home")
def home(request: Request):
    """
    This route is registered with both servers.
    """
    with Response(request) as response:
        response.send("Hello from home!")


id_address = str(wifi.radio.ipv4_address)

# Start the servers.

print(f"[bedroom_server] Listening on http://{id_address}:5000")
print(f"[office_server] Listening on http://{id_address}:8000")
bedroom_server.start(id_address, 5000)
office_server.start(id_address, 8000)

while True:
    try:
        # Process any waiting requests for both servers.
        bedroom_server.poll()
        office_server.poll()
    except OSError as error:
        print(error)
        continue
