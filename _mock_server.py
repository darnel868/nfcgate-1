#!/usr/bin/env python3
"""Temporary mock NFCGate server for testing nfcgate_monitor.py (delete after)."""
import socket, struct, threading

def read_frame(s):
    h = b""
    while len(h) < 4:
        c = s.recv(4 - len(h))
        if not c: return None
        h += c
    n = struct.unpack(">I", h)[0]
    body = b""
    while len(body) < n + 1:
        body += s.recv(n + 1 - len(body))
    return body[0], body[1:]

def write_frame(s, session, payload):
    s.sendall(struct.pack(">I", len(payload)) + bytes([session]) + payload)

# ServerData PSH with inner NFCData: READER(=0), INITIAL(=0), ts=1731628800000, APDU 00A404000E32506...
inner = (b"\x08\x00"          # field1 varint: data_source READER
         b"\x10\x00"          # field2 varint: data_type INITIAL
         b"\x18\xc0\xd4\x9a\x83\x0f"  # field4 varint: timestamp ms
         + b"\x1a\x0e"        # field3 len=14
         + bytes.fromhex("00A404000E32506E379D82C40088"))
psd = b"\x08\x00" + b"\x12" + bytes([len(inner)]) + inner  # opcode PSH, data

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 5599)); srv.listen(1)
print("mock listening on 127.0.0.1:5599"); srv.settimeout(8); conn, _ = srv.accept()
print("peer connected")

def serve():
    while True:
        f = read_frame(conn)
        if not f: break
        sess, payload = f
        fields = payload.hex()
        print(f"got frame session={sess} len={len(payload)} hex={fields}")
        # reply with the PSH APDU like a real bridge would
        write_frame(conn, 0, psd)

t = threading.Thread(target=serve); t.start(); t.join(timeout=5)
conn.close(); srv.close()
print("mock done")