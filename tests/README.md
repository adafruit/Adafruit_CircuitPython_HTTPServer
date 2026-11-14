# Tests

These tests run on CPython, not CircuitPython. No hardware or network is needed.

CI runs them on every push and pull request in two places:

- The standard Build CI workflow (`.github/workflows/build.yml`) runs `python -m pytest`.
- The Coverage workflow (`.github/workflows/coverage.yml`) runs them under coverage and puts the report in the job summary.

## Running

From the repository root:

```
pip install pytest coverage
python -m pytest
```

Use `python -m pytest`, not plain `pytest`. `python -m` puts the repository root on `sys.path`, so `import adafruit_httpserver` finds the working tree.

Coverage:

```
python -m coverage run -m pytest
python -m coverage report
```

The HTTPS test needs the `openssl` command to make a throwaway certificate. It is skipped if `openssl` is not installed.

## Layout

| File | Tests |
|---|---|
| `conftest.py` | Shared fixtures (see below) |
| `test_headers.py` | `Headers` |
| `test_route.py` | `Route`, `as_route()`, route registration and matching |
| `test_status.py` | `Status`, the status and method constants |
| `test_mime_types.py` | `MIMETypes` |
| `test_authentication.py` | `Basic`, `Token`, `Bearer`, `check_authentication()`, `require_authentication()` |
| `test_request.py` | `Request`, `QueryParams`, `FormData`, `File`, cookies, JSON |
| `test_response.py` | `Response`, `FileResponse`, `ChunkedResponse`, `JSONResponse`, `Redirect`, `SSEResponse` |
| `test_websocket.py` | `Websocket`: handshake, frames, protocol errors, closing |
| `test_server.py` | `Server` end to end: `poll()` results, routes modeled on `examples/`, static files, authentication, timeouts, `serve_forever()`, HTTPS |

Tests based on a file in `examples/` say which one.

## Fixtures

There are two ways of driving the library:

- **Real sockets.** `make_server` starts a `Server` on 127.0.0.1 with an OS-assigned port. `http` sends it a raw request, calls `poll()` once, and returns the parsed reply. This is single-threaded: the request is already queued in the kernel when `poll()` runs. The HTTPS and `serve_forever()` tests use a client thread instead.
- **Fake sockets.** `fake_socket` and `fake_pool` return in-memory stand-ins. They cover error paths that are hard to cause with real sockets:
  - EAGAIN (no data yet on a non-blocking socket)
  - ECONNRESET (connection reset by the peer)
  - timeouts
  - partial sends
  - websocket frames split across reads

Other fixtures:

- `make_request` builds a `Request` without any networking.
- `parse_response` parses raw response bytes.
- `tls_cert` makes the throwaway HTTPS certificate.
- An autouse fixture restores `MIMETypes` settings after each test, since they are class attributes.

## Known bugs and open questions

Library behavior that looks wrong is marked rather than asserted as correct:

- **`@pytest.mark.xfail(strict=True, reason=...)`** marks a known bug.
  - The test asserts the correct behavior, so it fails for now.
  - When the bug is fixed, the test passes. `strict=True` turns that unexpected pass into a failure.
  - Then remove the marker.
- **`@pytest.mark.skip(reason=...)`** marks a test that is not run. The reason starts with one of:
  - "Not run: bug." or "Not run: probable bug." for a bug the test shows.
  - "Not run: design question." for behavior that may be intended. The test shows the alternative.

To list them all with their reasons:

```
python -m pytest -rxs
```

## Coverage

`.coveragerc` in the repository root has the coverage settings:

- Branch coverage of `adafruit_httpserver`.
- Exclusions for code that cannot run on CPython, such as CircuitPython import fallbacks and SSL setup, with the reason for each.
- A comment listing lines that are still counted as missed, on purpose: a code path blocked by a known bug, and dead code.

A missed line that is not in that list is untested code.
