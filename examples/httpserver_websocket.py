# SPDX-FileCopyrightText: 2023 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

from time import monotonic
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, Websocket, GET


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


websocket: Websocket = None
next_message_time = monotonic()

HTML_TEMPLATE = """
<html lang="en">
    <head>
        <title>Websocket Client</title>
    </head>
    <body>
        <input id="message" type="text" placeholder="Message..."><br>
        <button id="send">Send</button>


        <script>
            const messageInput = document.querySelector('#message');
            const sendButton = document.querySelector('#send');

            let ws = new WebSocket('ws://' + location.host + '/connect-websocket');

            ws.onopen = () => console.log('WebSocket connection opened');
            ws.onerror = error => console.error('WebSocket error:', error);
            ws.onmessage = event => console.log('Received message from server: ', event.data);

            let interval = setInterval(() => ws.send("Hello from client"), 1000);

            ws.onclose = x => {
                console.log('WebSocket connection closed');
                clearInterval(interval);
            };

            sendButton.onclick = () => ws.send(messageInput.value);
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
        if (message := websocket.receive(True)) is not None:
            print("Received message from client:", message)

    # Send a message every second
    if websocket is not None and next_message_time < monotonic():
        websocket.send_message("Hello from server")
        next_message_time = monotonic() + 1
