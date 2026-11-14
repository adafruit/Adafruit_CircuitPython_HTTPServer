# SPDX-FileCopyrightText: Copyright (c) 2026 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Tests for adafruit_httpserver.Websocket.

The websocket's connection is a ``FakeSocket`` with ``eof=False``, so an empty receive queue
raises EAGAIN like a non-blocking socket with no data. Client frames are built by
``client_frame()``. Server frames are never masked.
"""

import errno
import threading

import pytest

from adafruit_httpserver import Websocket

# Sample handshake from RFC 6455 section 1.3.
SAMPLE_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
SAMPLE_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

HANDSHAKE_HEADERS = {
    "Host": "localhost",
    "Upgrade": "websocket",
    "Connection": "Upgrade",
    "Sec-WebSocket-Key": SAMPLE_KEY,
    "Sec-WebSocket-Version": "13",
}

TEXT, BINARY, CONT, CLOSE, PING, PONG = 1, 2, 0, 8, 9, 10

PROTOCOL_ERROR = 1002
POLICY_VIOLATION = 1008
MESSAGE_TOO_BIG = 1009


def handshake_request(headers=None):
    headers = HANDSHAKE_HEADERS if headers is None else headers
    lines = ["GET /connect-websocket HTTP/1.1"] + [f"{k}: {v}" for k, v in headers.items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def client_frame(
    opcode,
    payload=b"",
    *,
    fin=True,
    rsv=0,
    masked=True,
    length_bytes=None,
    mask=b"\x37\xfa\x21\x3d",
):
    """
    Build a client-to-server frame.

    ``length_bytes`` forces the 16-bit (2) or 64-bit (8) extended length encoding.
    """
    if isinstance(payload, str):
        payload = payload.encode()

    frame = bytearray([(0x80 if fin else 0) | rsv | opcode])
    mask_bit = 0x80 if masked else 0
    length = len(payload)

    if length_bytes is None:
        length_bytes = 0 if length < 126 else 2 if length < 65536 else 8
    if length_bytes == 0:
        frame.append(mask_bit | length)
    else:
        frame.append(mask_bit | (126 if length_bytes == 2 else 127))
        frame += length.to_bytes(length_bytes, "big")

    if masked:
        frame += mask
        frame += bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    else:
        frame += payload
    return bytes(frame)


def server_frame(opcode, payload=b""):
    """Expected unmasked server-to-client frame."""
    return Websocket._prepare_frame(opcode, payload)


def close_frame(code=None, reason=""):
    payload = b"" if code is None else code.to_bytes(2, "big") + reason.encode()
    return server_frame(CLOSE, payload)


@pytest.fixture
def ws_request(make_request, fake_socket):
    """Factory returning ``(request, conn)`` for a websocket handshake request."""

    def factory(headers=None):
        conn = fake_socket(eof=False)
        return make_request(handshake_request(headers), conn=conn), conn

    return factory


@pytest.fixture
def websocket(ws_request):
    """``(websocket, conn)`` after the 101 response has been sent. ``conn.sent`` is cleared."""
    request, conn = ws_request()
    ws = Websocket(request)
    ws._send()
    del conn.sent[:]
    return ws, conn


# Handshake


def test_handshake(ws_request, parse_response):
    request, conn = ws_request()
    ws = Websocket(request)
    ws._send()
    reply = parse_response(bytes(conn.sent))

    assert reply.status_line == "HTTP/1.1 101 Switching Protocols"
    assert reply.header("Upgrade") == "websocket"
    assert reply.header("Connection") == "Upgrade"
    assert reply.header("Sec-WebSocket-Accept") == SAMPLE_ACCEPT
    assert reply.header("Content-Length") is None
    assert reply.body == b""
    assert conn.blocking is False
    assert not conn.closed
    assert ws.closed is False


@pytest.mark.xfail(
    strict=True,
    reason="Websocket sets Content-Type to None so the header is left out. Headers.copy() turns "
    "None into the string 'None', so the 101 response includes 'content-type: None'.",
)
def test_handshake_has_no_content_type(ws_request, parse_response):
    request, conn = ws_request()
    Websocket(request)._send()

    assert parse_response(bytes(conn.sent)).header("Content-Type") is None


def test_handshake_firefox_connection_header(ws_request):
    # Firefox sends "Connection: keep-alive, Upgrade".
    request, _ = ws_request({**HANDSHAKE_HEADERS, "Connection": "keep-alive, Upgrade"})

    Websocket(request)  # Does not raise.


@pytest.mark.parametrize(
    "headers",
    [
        {k: v for k, v in HANDSHAKE_HEADERS.items() if k != "Upgrade"},
        {k: v for k, v in HANDSHAKE_HEADERS.items() if k != "Connection"},
        {k: v for k, v in HANDSHAKE_HEADERS.items() if k != "Sec-WebSocket-Key"},
        {**HANDSHAKE_HEADERS, "Upgrade": "h2c"},
        {**HANDSHAKE_HEADERS, "Connection": "keep-alive"},
    ],
    ids=["no-upgrade", "no-connection", "no-key", "wrong-upgrade", "wrong-connection"],
)
def test_handshake_not_a_websocket_request(ws_request, headers):
    request, _ = ws_request(headers)

    with pytest.raises(ValueError, match="Request does not initiate websocket handshake"):
        Websocket(request)


# Receiving


def test_receive_nothing_available(websocket):
    ws, conn = websocket

    assert ws.receive() is None
    assert not ws.closed
    assert conn.sent == b""


def test_receive_text(websocket):
    # The websocket example's client sends a color picker value.
    ws, conn = websocket
    conn.feed(client_frame(TEXT, "#ff8000"))

    assert ws.receive() == "#ff8000"


def test_receive_utf8_text(websocket):
    ws, conn = websocket
    conn.feed(client_frame(TEXT, "héllo ✓"))

    assert ws.receive() == "héllo ✓"


def test_receive_binary(websocket):
    ws, conn = websocket
    conn.feed(client_frame(BINARY, b"\x00\x01\xff"))

    assert ws.receive() == b"\x00\x01\xff"


@pytest.mark.parametrize(("size", "length_bytes"), [(126, 2), (4096, 2), (300, 8)])
def test_receive_extended_lengths(websocket, size, length_bytes):
    ws, conn = websocket
    payload = bytes(i % 251 for i in range(size))
    conn.feed(client_frame(BINARY, payload, length_bytes=length_bytes))

    assert ws.receive() == payload


def test_receive_frame_split_across_reads(websocket):
    ws, conn = websocket
    frame = client_frame(TEXT, "split" * 40)
    conn.feed(*(frame[i : i + 1] for i in range(len(frame))))

    assert ws.receive() == "split" * 40


@pytest.mark.skip(
    reason="Not run: bug. _recv_exact() retries EAGAIN (no data yet) in a busy loop with no "
    "timeout. A client that stops partway through a frame blocks receive() forever, and the "
    "server with it. If run, the test fails after about 0.5 s instead of hanging."
)
def test_receive_stalled_mid_frame_does_not_hang(websocket):
    ws, conn = websocket
    frame = client_frame(TEXT, "partial")
    conn.feed(frame[:5])  # Frame header and 3 of the 4 mask bytes, then nothing.

    thread = threading.Thread(target=ws.receive, daemon=True)
    thread.start()
    thread.join(timeout=0.5)
    stalled = thread.is_alive()

    # Let a stuck receive() finish so no spinning thread outlives the test.
    conn.feed(frame[5:])
    thread.join(timeout=5)

    assert not stalled, "receive() was still waiting for the rest of the frame"


def test_receive_eagain_partway_through_frame_then_rest_arrives(websocket):
    ws, conn = websocket
    frame = client_frame(TEXT, "resumed")
    conn.feed(frame[:3], OSError(errno.EAGAIN, "no data yet"), frame[3:])

    assert ws.receive() == "resumed"


def test_receive_several_frames_in_one_read(websocket):
    ws, conn = websocket
    conn.feed(client_frame(TEXT, "one") + client_frame(TEXT, "two"))

    assert ws.receive() == "one"
    assert ws.receive() == "two"
    assert ws.receive() is None


def test_receive_fragmented_message(websocket):
    ws, conn = websocket
    conn.feed(
        client_frame(TEXT, "Hel", fin=False),
        client_frame(CONT, "lo ", fin=False),
        client_frame(CONT, "world"),
    )

    assert ws.receive() is None
    assert ws.receive() is None
    assert ws.receive() == "Hello world"
    assert ws.receive() is None


def test_receive_fragmented_binary_with_ping_between_fragments(websocket):
    ws, conn = websocket
    conn.feed(
        client_frame(BINARY, b"\x01", fin=False),
        client_frame(PING, b"ping"),
        client_frame(CONT, b"\x02"),
    )

    assert ws.receive() is None
    assert ws.receive() is None
    assert conn.sent == server_frame(PONG, b"ping")
    assert ws.receive() == b"\x01\x02"


def test_ping_is_answered_with_pong(websocket):
    ws, conn = websocket
    conn.feed(client_frame(PING, b"are you there"))

    assert ws.receive() is None
    assert conn.sent == server_frame(PONG, b"are you there")
    assert not ws.closed


def test_pong_is_ignored(websocket):
    ws, conn = websocket
    conn.feed(client_frame(PONG, b"x"))

    assert ws.receive() is None
    assert conn.sent == b""
    assert not ws.closed


@pytest.mark.parametrize(("code", "reason"), [(None, ""), (1000, ""), (1001, "going away")])
def test_close_from_client_is_echoed(websocket, code, reason):
    ws, conn = websocket
    payload = b"" if code is None else code.to_bytes(2, "big") + reason.encode()
    conn.feed(client_frame(CLOSE, payload))

    assert ws.receive() is None
    assert conn.sent == close_frame(code, reason)
    assert ws.closed
    assert conn.closed


@pytest.mark.xfail(
    strict=True,
    reason="receive() should close when the client disconnects. _recv_exact() signals a "
    "disconnect with OSError(ENOTCONN), but passes only one argument. CPython sets errno only for "
    "the two-argument form, so receive() doesn't recognize the disconnect and raises.",
)
def test_client_disconnect_closes(make_request, fake_socket):
    conn = fake_socket(eof=True)
    ws = Websocket(make_request(handshake_request(), conn=conn))

    assert ws.receive() is None
    assert ws.closed
    assert conn.closed


@pytest.mark.parametrize(
    "received",
    [
        pytest.param(
            b"\x81",
            marks=pytest.mark.xfail(
                strict=True,
                reason="receive() should close when the client disconnects. _recv_exact() "
                "signals a disconnect with OSError(ENOTCONN), but passes only one argument. "
                "CPython sets errno only for the two-argument form, so receive() doesn't "
                "recognize the disconnect and raises.",
            ),
            id="in-header",
        ),
        pytest.param(client_frame(BINARY, bytes(200))[:3], id="in-16-bit-length"),
        pytest.param(client_frame(BINARY, bytes(300), length_bytes=8)[:6], id="in-64-bit-length"),
        pytest.param(client_frame(TEXT, "x")[:4], id="in-mask"),
    ],
)
def test_client_closes_partway_through_frame(websocket, received):
    ws, conn = websocket
    conn.feed(received)
    conn.eof = True

    assert ws.receive() is None
    assert ws.closed
    assert conn.closed


def test_receive_timeout_returns_none(websocket):
    ws, conn = websocket
    conn.feed(TimeoutError(errno.ETIMEDOUT, "timed out"))

    assert ws.receive() is None
    assert not ws.closed


def test_receive_other_socket_error_raises(websocket):
    ws, conn = websocket
    conn.feed(OSError(errno.EBADF, "bad file descriptor"))

    with pytest.raises(OSError, match="bad file descriptor"):
        ws.receive()


@pytest.mark.xfail(
    strict=True,
    reason="receive() raises when the client resets the connection (ECONNRESET). It should "
    "close, as it does for a disconnect.",
)
def test_receive_connection_reset_closes(websocket):
    ws, conn = websocket
    conn.feed(ConnectionResetError(errno.ECONNRESET, "reset"))

    assert ws.receive(fail_silently=True) is None
    assert ws.closed


# Protocol errors: the server closes with a status code


def protocol_error_cases():
    too_big = Websocket.MESSAGE_MAX_SIZE_BYTES + 1
    return [
        pytest.param([client_frame(TEXT, "hi", masked=False)], PROTOCOL_ERROR, id="unmasked"),
        pytest.param(
            # Only the header is needed: the length is checked before the payload is read.
            [client_frame(BINARY, bytes(too_big))[:4]],
            MESSAGE_TOO_BIG,
            id="too-big",
        ),
        pytest.param([client_frame(TEXT, b"\xff\xfe")], PROTOCOL_ERROR, id="bad-utf8"),
        pytest.param(
            [client_frame(TEXT, b"ok", fin=False), client_frame(CONT, b"\xff")],
            PROTOCOL_ERROR,
            id="bad-utf8-fragmented",
        ),
        pytest.param([client_frame(CONT, "x")], PROTOCOL_ERROR, id="cont-without-start"),
        pytest.param(
            [client_frame(TEXT, "a", fin=False), client_frame(TEXT, "b")],
            PROTOCOL_ERROR,
            id="new-message-during-fragments",
        ),
        pytest.param([client_frame(3, "x")], PROTOCOL_ERROR, id="reserved-opcode"),
        pytest.param([client_frame(PING, "x", fin=False)], PROTOCOL_ERROR, id="fragmented-ping"),
        pytest.param([client_frame(PING, bytes(126))], PROTOCOL_ERROR, id="control-too-long"),
        pytest.param(
            # 64-bit length with the most significant bit set (RFC 6455 section 5.2).
            [bytes([0x80 | BINARY, 0x80 | 127]) + b"\x80" + bytes(7)],
            PROTOCOL_ERROR,
            id="64-bit-length-top-bit",
        ),
        pytest.param([client_frame(CLOSE, b"\x03")], PROTOCOL_ERROR, id="close-one-byte"),
        pytest.param(
            [client_frame(CLOSE, b"\x03\xe8\xff")], PROTOCOL_ERROR, id="close-bad-utf8-reason"
        ),
    ]


@pytest.mark.parametrize(("frames", "code"), protocol_error_cases())
def test_protocol_error_closes_with_code(websocket, frames, code):
    ws, conn = websocket
    conn.feed(*frames)

    for _ in frames:
        if ws.closed:
            break
        assert ws.receive() is None

    assert ws.closed
    assert conn.closed
    assert conn.sent.endswith(close_frame(code))


def test_too_many_fragments(websocket):
    ws, conn = websocket
    ws.MESSAGE_MAX_FRAGMENTS = 3
    conn.feed(*(client_frame(TEXT if i == 0 else CONT, "x", fin=False) for i in range(4)))

    for _ in range(3):
        assert ws.receive() is None
    assert not ws.closed

    assert ws.receive() is None
    assert ws.closed
    assert conn.sent == close_frame(POLICY_VIOLATION)


def test_fragmented_messages_disallowed(websocket):
    ws, conn = websocket
    ws.MESSAGE_MAX_FRAGMENTS = 1
    conn.feed(client_frame(TEXT, "x", fin=False))

    assert ws.receive() is None
    assert ws.closed
    assert conn.sent == close_frame(POLICY_VIOLATION)


def test_fragmented_message_too_big(websocket):
    ws, conn = websocket
    ws.MESSAGE_MAX_SIZE_BYTES = 10
    conn.feed(client_frame(TEXT, "123456", fin=False), client_frame(CONT, "789012"))

    assert ws.receive() is None
    assert ws.receive() is None
    assert ws.closed
    assert conn.sent == close_frame(MESSAGE_TOO_BIG)


def test_fragment_timeout(websocket):
    ws, conn = websocket
    ws.MESSAGE_FRAGMENT_TIMEOUT_NS = -1  # Any wait exceeds it.
    conn.feed(client_frame(TEXT, "partial", fin=False))

    assert ws.receive() is None
    assert not ws.closed

    assert ws.receive() is None  # No more data: the fragment has timed out.
    assert ws.closed
    assert conn.sent == close_frame(POLICY_VIOLATION)


def test_fragment_timeout_noticed_on_next_frame(websocket):
    ws, conn = websocket
    ws.MESSAGE_FRAGMENT_TIMEOUT_NS = -1  # Any wait exceeds it.
    conn.feed(client_frame(TEXT, "late", fin=False), client_frame(CONT, "r"))

    assert ws.receive() is None
    assert ws.receive() is None
    assert ws.closed
    assert conn.sent == close_frame(POLICY_VIOLATION)


def test_waiting_for_next_fragment_within_timeout(websocket):
    ws, conn = websocket
    conn.feed(client_frame(TEXT, "a", fin=False))

    assert ws.receive() is None
    assert ws.receive() is None  # No data yet; still within the fragment timeout.
    assert not ws.closed

    conn.feed(client_frame(CONT, "b"))
    assert ws.receive() == "ab"


@pytest.mark.xfail(
    strict=True,
    reason="Frames with a reserved bit (RSV1-RSV3) set are accepted. RFC 6455 section 5.2 "
    "requires failing the connection when no negotiated extension defines those bits.",
)
def test_rsv_bits_close_connection(websocket):
    ws, conn = websocket
    conn.feed(client_frame(TEXT, "hi", rsv=0x40))

    assert ws.receive() is None
    assert ws.closed
    assert conn.sent == close_frame(PROTOCOL_ERROR)


# Sending


def test_send_text_and_binary(websocket):
    ws, conn = websocket

    ws.send_message("23.5")
    ws.send_message(b"\x00\xff")

    assert conn.sent == b"\x81\x0423.5" + b"\x82\x02\x00\xff"


def test_send_explicit_opcode(websocket):
    ws, conn = websocket

    ws.send_message(b"x", PING)

    assert conn.sent == b"\x89\x01x"


@pytest.mark.parametrize(
    ("size", "length_header"),
    [
        (0, b"\x00"),
        (125, b"\x7d"),
        (126, b"\x7e\x00\x7e"),
        (65535, b"\x7e\xff\xff"),
        (65536, b"\x7f\x00\x00\x00\x00\x00\x01\x00\x00"),
    ],
)
def test_send_length_encodings(websocket, size, length_header):
    ws, conn = websocket

    ws.send_message(b"a" * size)

    assert conn.sent == b"\x82" + length_header + b"a" * size


def test_send_partial_writes(make_request, fake_socket):
    conn = fake_socket(eof=False, max_send=7)
    ws = Websocket(make_request(handshake_request(), conn=conn))

    ws.send_message("x" * 100)

    assert conn.sent.endswith(server_frame(TEXT, b"x" * 100))


def test_send_broken_pipe(websocket):
    ws, conn = websocket
    conn._send_errors = [BrokenPipeError(errno.EPIPE, "broken pipe")]

    with pytest.raises(BrokenPipeError):
        ws.send_message("x")

    conn._send_errors = [BrokenPipeError(errno.EPIPE, "broken pipe")]
    ws.send_message("x", fail_silently=True)  # Does not raise.


# Closing from the server


def test_close(websocket):
    ws, conn = websocket

    ws.close()

    assert ws.closed
    assert conn.closed
    assert conn.sent == close_frame()


def test_close_with_code_and_reason(websocket):
    ws, conn = websocket

    ws.close(1000, "done")

    assert conn.sent == close_frame(1000, "done")


def test_close_reason_truncated_to_control_frame_limit(websocket):
    ws, conn = websocket

    ws.close(1000, "r" * 200)

    assert conn.sent == server_frame(CLOSE, b"\x03\xe8" + b"r" * 123)


def test_close_twice_sends_once(websocket):
    ws, conn = websocket

    ws.close()
    ws.close()

    assert conn.sent == close_frame()


@pytest.mark.parametrize(
    "error",
    [
        # CPython turns OSError(EPIPE) into BrokenPipeError,
        # which send_message(fail_silently=True) catches.
        OSError(errno.EPIPE, "broken pipe"),
        # Other errors are caught in close() itself.
        OSError(errno.EBADF, "bad file descriptor"),
    ],
    ids=["EPIPE", "EBADF"],
)
def test_close_when_send_fails(websocket, error):
    ws, conn = websocket
    conn._send_errors = [error]

    ws.close()  # Does not raise.

    assert ws.closed
    assert conn.closed


def test_use_after_close(websocket):
    ws, _ = websocket
    ws.close()

    with pytest.raises(RuntimeError, match="cannot receive"):
        ws.receive()
    with pytest.raises(RuntimeError, match="cannot send"):
        ws.send_message("x")

    assert ws.receive(fail_silently=True) is None
    assert ws.send_message("x", fail_silently=True) is None
