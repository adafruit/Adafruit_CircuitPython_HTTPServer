# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import json
import microcontroller
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


@server.route("/cpu-information")
def cpu_information_handler(request: Request):
    """
    Return the current CPU temperature, frequency, and voltage as JSON.
    """

    data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }

    with Response(request, content_type="application/json") as response:
        response.send(json.dumps(data))


server.serve_forever(str(wifi.radio.ipv4_address))
