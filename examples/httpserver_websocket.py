# SPDX-FileCopyrightText: 2023 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

from time import monotonic
import board
import microcontroller
import neopixel
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, Websocket, GET


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)


websocket: Websocket = None
next_message_time = monotonic()

HTML_TEMPLATE = """
<html lang="en">
    <head>
        <title>Websocket Client</title>
    </head>
    <body>
        <p>CPU temperature: <strong>-</strong>&deg;C</p>
        <p>NeoPixel Color: <input type="color"></p>
        <script>
            const cpuTemp = document.querySelector('strong');
            const colorPicker = document.querySelector('input[type="color"]');

            let ws = new WebSocket('ws://' + location.host + '/connect-websocket');

            ws.onopen = () => console.log('WebSocket connection opened');
            ws.onclose = () => console.log('WebSocket connection closed');
            ws.onmessage = event => cpuTemp.textContent = event.data;
            ws.onerror = error => cpuTemp.textContent = error;

            colorPicker.oninput = debounce(() => ws.send(colorPicker.value), 200);

            function debounce(callback, delay = 1000) {
                let timeout
                return (...args) => {
                    clearTimeout(timeout)
                    timeout = setTimeout(() => {
                    callback(...args)
                  }, delay)
                }
            }
        </script>
    </body>
</html>
"""


@server.route("/client", GET)
def client(request: Request):
    return Response(request, HTML_TEMPLATE, content_type="text/html")


@server.route("/connect-websocket", GET)
def connect_client(request: Request):
    global websocket  # pylint: disable=global-statement

    if websocket is not None:
        websocket.close()  # Close any existing connection

    websocket = Websocket(request)

    return websocket


server.start(str(wifi.radio.ipv4_address))
while True:
    server.poll()

    # Check for incoming messages from client
    if websocket is not None:
        if (data := websocket.receive(True)) is not None:
            r, g, b = int(data[1:3], 16), int(data[3:5], 16), int(data[5:7], 16)
            pixel.fill((r, g, b))

    # Send a message every second
    if websocket is not None and next_message_time < monotonic():
        cpu_temp = round(microcontroller.cpu.temperature, 2)
        websocket.send_message(str(cpu_temp))
        next_message_time = monotonic() + 1
