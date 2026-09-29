"""The one route out of the sandbox: an allowlisting proxy on a unix socket.

Two roles in one file, both stdlib-only so they run with the host's bare `python3`
(the sandbox has no site-packages) and start in tens of milliseconds:

    python3 sandbox_proxy.py host    <unix-socket> <allowlist>   # outside the namespace
    python3 sandbox_proxy.py forward <unix-socket> <tcp-port>    # inside it, on 127.0.0.1

`codex_sandbox.sh` unshares the network namespace, so inside there is a loopback and
nothing else -- no route, no DNS. `forward` listens on 127.0.0.1:<port> in there and
pipes each connection to the unix socket, which is bind-mounted in from the host;
`host` answers on that socket and lets HTTP CONNECT (TLS tunnels) and plain HTTP
requests through to hosts on the allowlist, and nothing else. Codex is pointed at it
with HTTPS_PROXY/HTTP_PROXY. This is upstream PRO-LONG's "no network except a proxy to
the model API" (`--internal` docker network + squid allowlist), rebuilt without a
container network because rootless podman here has no CNI plugins and bwrap has no
networking at all -- and it is the same design on apptainer `--network none`.

The allowlist is a comma-separated list of `host:port` entries. A leading dot matches
the domain and every subdomain (`.chatgpt.com:443`). Plain-HTTP entries are how a local
model server (`--codex-base-url http://gh142:30000/v1`) is reached: the request line
arrives in absolute form (`POST http://gh142:30000/v1/responses HTTP/1.1`) and is
rewritten to origin form before it is forwarded, request by request, so keep-alive
works. Every decision is logged to stderr as `sandbox-proxy: ALLOW|DENY host:port`, and
the wrapper's stderr is what `CodexTurn` saves as `turn_NNNN.stderr.txt`, so the
evidence of what left the sandbox lands next to the turn that sent it.

The `host` role dies with its parent (PR_SET_PDEATHSIG, plus a ppid poll for the
paths that signal does not cover), so a runner timeout that kills the wrapper does not
leave a proxy behind.
"""
from __future__ import annotations

import asyncio
import ctypes
import os
import signal
import sys
from urllib.parse import urlsplit

_HEAD_LIMIT = 64 * 1024


def _log(msg: str) -> None:
    sys.stderr.write(f"sandbox-proxy: {msg}\n")
    sys.stderr.flush()


class Allowlist:
    def __init__(self, spec: str) -> None:
        self.entries: list[tuple[str, int]] = []
        for raw in spec.split(","):
            raw = raw.strip().lower()
            if not raw:
                continue
            host, _, port = raw.rpartition(":")
            if not host or not port.isdigit():
                raise SystemExit(f"sandbox-proxy: bad allowlist entry {raw!r} (want host:port)")
            self.entries.append((host, int(port)))
        if not self.entries:
            raise SystemExit("sandbox-proxy: empty allowlist")

    def allows(self, host: str, port: int) -> bool:
        host = host.lower().rstrip(".")
        for pattern, p in self.entries:
            if p != port:
                continue
            if pattern.startswith("."):
                if host == pattern[1:] or host.endswith(pattern):
                    return True
            elif host == pattern:
                return True
        return False


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _read_head(reader: asyncio.StreamReader) -> bytes:
    """One request head, through the blank line. Empty bytes at a clean EOF."""
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = await reader.read(4096)
        if not chunk:
            return b""
        head += chunk
        if len(head) > _HEAD_LIMIT:
            raise ValueError("request head too large")
    return head


def _split_head(head: bytes) -> tuple[bytes, list[bytes], bytes]:
    """(request line, header lines, leftover bytes after the blank line)."""
    end = head.index(b"\r\n\r\n") + 4
    lines = head[:end].split(b"\r\n")
    return lines[0], [ln for ln in lines[1:] if ln], head[end:]


async def _copy_body(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                     headers: list[bytes], leftover: bytes) -> bytes:
    """Forward exactly one request body; return bytes that belong to the *next* request."""
    length = None
    chunked = False
    for ln in headers:
        name, _, value = ln.partition(b":")
        name = name.strip().lower()
        if name == b"content-length":
            length = int(value.strip())
        elif name == b"transfer-encoding" and b"chunked" in value.lower():
            chunked = True
    buf = leftover
    if length is not None:
        while len(buf) < length:
            chunk = await reader.read(65536)
            if not chunk:
                break
            buf += chunk
        writer.write(buf[:length])
        await writer.drain()
        return buf[length:]
    if chunked:
        # Copy chunks until the terminating zero-size chunk and its trailer.
        while True:
            while b"\r\n" not in buf:
                chunk = await reader.read(65536)
                if not chunk:
                    return b""
                buf += chunk
            line, _, rest = buf.partition(b"\r\n")
            size = int(line.split(b";")[0].strip() or b"0", 16)
            need = size + 2                       # data + CRLF
            while len(rest) < need:
                chunk = await reader.read(65536)
                if not chunk:
                    return b""
                rest += chunk
            writer.write(line + b"\r\n" + rest[:need])
            await writer.drain()
            buf = rest[need:]
            if size == 0:
                return buf
    return buf


async def _handle_host(allow: Allowlist, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter) -> None:
    upstream_w: asyncio.StreamWriter | None = None
    try:
        head = await _read_head(reader)
        if not head:
            return
        line, headers, leftover = _split_head(head)
        parts = line.decode("latin-1").split()
        if len(parts) < 2:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return
        method, target = parts[0], parts[1]

        if method == "CONNECT":
            host, _, port_s = target.rpartition(":")
            port = int(port_s) if port_s.isdigit() else 443
            if not allow.allows(host, port):
                _log(f"DENY {host}:{port}")
                writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                return
            _log(f"ALLOW {host}:{port}")
            up_r, up_w = await asyncio.open_connection(host, port)
            upstream_w = up_w
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            if leftover:
                up_w.write(leftover)
            await asyncio.gather(_pipe(reader, up_w), _pipe(up_r, writer))
            return

        # Plain HTTP, absolute-form request target. Rewrite to origin form per request
        # and keep the upstream connection for the next one on this client connection.
        url = urlsplit(target)
        if url.scheme != "http" or not url.hostname:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return
        host, port = url.hostname, url.port or 80
        if not allow.allows(host, port):
            _log(f"DENY {host}:{port}")
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        _log(f"ALLOW {host}:{port} (http)")
        up_r, up_w = await asyncio.open_connection(host, port)
        upstream_w = up_w
        response_task = asyncio.ensure_future(_pipe(up_r, writer))
        while True:
            path = (url.path or "/") + (f"?{url.query}" if url.query else "")
            proto = parts[2] if len(parts) > 2 else "HTTP/1.1"
            out = [f"{method} {path} {proto}".encode("latin-1")]
            has_host = False
            for ln in headers:
                name = ln.split(b":", 1)[0].strip().lower()
                if name in (b"proxy-connection", b"proxy-authorization"):
                    continue
                if name == b"host":
                    has_host = True
                out.append(ln)
            if not has_host:
                out.append(f"Host: {host}:{port}".encode("latin-1"))
            up_w.write(b"\r\n".join(out) + b"\r\n\r\n")
            await up_w.drain()
            leftover = await _copy_body(reader, up_w, headers, leftover)
            # Next request on the same connection, if any.
            head = leftover if b"\r\n\r\n" in leftover else leftover + await _read_head(reader)
            if not head or b"\r\n\r\n" not in head:
                break
            line, headers, leftover = _split_head(head)
            parts = line.decode("latin-1").split()
            if len(parts) < 2:
                break
            method, target = parts[0], parts[1]
            url = urlsplit(target)
            if url.scheme != "http" or (url.hostname, url.port or 80) != (host, port):
                _log(f"DENY {url.hostname}:{url.port or 80} (host changed on a kept-alive connection)")
                break
        response_task.cancel()
    except (ConnectionError, asyncio.IncompleteReadError, OSError, ValueError) as e:
        _log(f"ERROR {e}")
    finally:
        for w in (writer, upstream_w):
            if w is not None:
                try:
                    w.close()
                except Exception:
                    pass


def _die_with_parent() -> None:
    parent = os.getppid()
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGTERM)          # PR_SET_PDEATHSIG
    except Exception:
        pass
    if os.getppid() != parent:                 # parent already gone between fork and prctl
        raise SystemExit(0)

    async def poll() -> None:
        while True:
            await asyncio.sleep(2)
            if os.getppid() != parent:
                raise SystemExit(0)
    asyncio.ensure_future(poll())


async def _serve_host(sock: str, allow: Allowlist) -> None:
    if os.path.exists(sock):
        os.unlink(sock)
    server = await asyncio.start_unix_server(
        lambda r, w: _handle_host(allow, r, w), sock)
    os.chmod(sock, 0o600)
    _die_with_parent()
    _log(f"listening on {sock}; allow={','.join(f'{h}:{p}' for h, p in allow.entries)}")
    async with server:
        await server.serve_forever()


async def _serve_forward(sock: str, port: int) -> None:
    async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        try:
            ur, uw = await asyncio.open_unix_connection(sock)
        except OSError:
            w.close()
            return
        await asyncio.gather(_pipe(r, uw), _pipe(ur, w))
    server = await asyncio.start_server(handle, "127.0.0.1", port)
    async with server:
        await server.serve_forever()


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in ("host", "forward"):
        sys.stderr.write(__doc__ or "")
        return 2
    role, sock, arg = argv[1], argv[2], argv[3]
    try:
        if role == "host":
            asyncio.run(_serve_host(sock, Allowlist(arg)))
        else:
            asyncio.run(_serve_forward(sock, int(arg)))
    except KeyboardInterrupt:
        pass
    finally:
        if role == "host":
            try:
                os.unlink(sock)
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
