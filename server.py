"""Neon Walk server: serves the site from ./public and relays walker positions over WebSocket.

Standard library only (Python 3.9+), so it runs on Render, a Mac or any host without installing packages.
  python3 server.py            -> http://localhost:8000
  PORT=10000 python3 server.py -> what Render sets automatically
"""
import asyncio
import base64
import hashlib
import json
import mimetypes
import os
import secrets
import struct
import time
from pathlib import Path

ROOT = (Path(__file__).parent / "public").resolve()
PORT = int(os.environ.get("PORT", "8000"))
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_CLIENTS = 150
MAX_FRAME = 4096          # one presence message is ~150 bytes
MAX_MSGS_PER_SEC = 30
mimetypes.add_type("audio/mpeg", ".mp3")

clients = {}  # id -> {"writer": StreamWriter, "presence": dict | None}


# ---------- WebSocket frames ----------
def frame(data: bytes, opcode: int = 0x1) -> bytes:
    n = len(data)
    if n < 126:
        head = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 65536:
        head = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    return head + data


async def read_frame(reader):
    b1, b2 = await reader.readexactly(2)
    opcode, masked, n = b1 & 0x0F, b2 & 0x80, b2 & 0x7F
    if n == 126:
        (n,) = struct.unpack("!H", await reader.readexactly(2))
    elif n == 127:
        (n,) = struct.unpack("!Q", await reader.readexactly(8))
    if n > MAX_FRAME or not masked:
        raise ConnectionError("frame too large or unmasked")
    mask = await reader.readexactly(4)
    data = bytearray(await reader.readexactly(n))
    for i in range(n):
        data[i] ^= mask[i % 4]
    return opcode, bytes(data)


async def send(cid, msg: dict):
    c = clients.get(cid)
    if not c:
        return
    try:
        c["writer"].write(frame(json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode()))
        await asyncio.wait_for(c["writer"].drain(), timeout=5)
    except Exception:
        drop(cid)


async def broadcast(msg: dict, skip=None):
    await asyncio.gather(*(send(cid, msg) for cid in list(clients) if cid != skip))


def drop(cid):
    c = clients.pop(cid, None)
    if c:
        try:
            c["writer"].close()
        except Exception:
            pass
        asyncio.ensure_future(broadcast({"t": "leave", "id": cid}))


def clean_presence(d):
    """Keep only the fields the page uses, with sane types and sizes."""
    if not isinstance(d, dict):
        return None
    out = {}
    if d.get("k") in ("man", "woman"):
        out["k"] = d["k"]
    if d.get("w") in ("s", "c", "sel"):
        out["w"] = d["w"]
    for key in ("x", "z", "y"):
        v = d.get(key)
        if isinstance(v, (int, float)) and abs(v) < 1000:
            out[key] = round(float(v), 2)
    out["m"] = 1 if d.get("m") == 1 else 0
    name = d.get("n")
    if isinstance(name, str):
        out["n"] = "".join(ch for ch in name if ch.isprintable() and ch not in "<>")[:14]
    return out


async def websocket(reader, writer, headers):
    key = headers.get("sec-websocket-key", "")
    if len(clients) >= MAX_CLIENTS or not key:
        writer.write(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
    writer.write(
        "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode()
    )
    await writer.drain()
    cid = secrets.token_hex(6)
    clients[cid] = {"writer": writer, "presence": None}
    await send(cid, {"t": "hello", "id": cid,
                     "peers": {k: v["presence"] for k, v in clients.items() if k != cid and v["presence"]}})
    window_start, count = time.monotonic(), 0
    try:
        while cid in clients:
            opcode, data = await asyncio.wait_for(read_frame(reader), timeout=60)
            if opcode == 0x8:  # close
                break
            if opcode == 0x9:  # ping
                writer.write(frame(data, 0xA))
                continue
            if opcode != 0x1:
                continue
            now = time.monotonic()
            if now - window_start > 1:
                window_start, count = now, 0
            count += 1
            if count > MAX_MSGS_PER_SEC:
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if msg.get("t") == "p":
                p = clean_presence(msg.get("d"))
                if p is not None:
                    clients[cid]["presence"] = p
                    await broadcast({"t": "p", "id": cid, "d": p}, skip=cid)
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError):
        pass
    finally:
        drop(cid)


# ---------- static files ----------
async def static(writer, method, path):
    path = path.split("?", 1)[0].split("#", 1)[0]
    if path == "/healthz":
        body, ctype, status = b"ok", "text/plain", "200 OK"
    else:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (ROOT / rel).resolve()
        if ROOT not in target.parents and target != ROOT or not target.is_file():
            body, ctype, status = b"Not found", "text/plain", "404 Not Found"
        else:
            body = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            status = "200 OK"
    cache = "no-cache" if ctype.startswith("text/html") else "public, max-age=86400"
    head = (f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
            f"Cache-Control: {cache}\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n").encode()
    writer.write(head if method == "HEAD" else head + body)
    await writer.drain()
    writer.close()


async def handle(reader, writer):
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
    except Exception:
        writer.close()
        return
    if len(raw) > 16384:
        writer.close()
        return
    lines = raw.decode("latin-1").split("\r\n")
    try:
        method, path, _ = lines[0].split(" ", 2)
    except ValueError:
        writer.close()
        return
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    if path.startswith("/ws") and headers.get("upgrade", "").lower() == "websocket":
        await websocket(reader, writer, headers)
    elif method in ("GET", "HEAD"):
        await static(writer, method, path)
    else:
        writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    print(f"Neon Walk on http://localhost:{PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
