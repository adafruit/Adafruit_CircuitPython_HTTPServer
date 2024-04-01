# SPDX-FileCopyrightText: 2024 DJDevon3
# SPDX-License-Identifier: MIT
# Coded for Circuit Python 9.
"""HTTP Server Simpletest with Connection Manager"""
# pylint: disable=import-error

import os

import adafruit_connection_manager
import wifi

from adafruit_httpserver import Server, Request, Response

# Get WiFi details, ensure these are setup in settings.toml
ssid = os.getenv("WIFI_SSID")
password = os.getenv("WIFI_PASSWORD")

print("Connecting to WiFi...")
wifi.radio.connect(ssid, password)
print("✅ Wifi!")

# Initalize Wifi, Socket Pool, Request Session
pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
server = Server(pool, "/static", debug=True)


@server.route("/")
def base(request: Request):
    """Serve a default static plain text message"""
    return Response(request, "Hello from the CircuitPython HTTP Server!")


server.serve_forever(str(wifi.radio.ipv4_address))
