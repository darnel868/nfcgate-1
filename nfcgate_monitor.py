#!/usr/bin/env python3
"""
NFCGate Live Monitor  (pure Python, no dependencies)

Connects to a running NFCGate bridge server as an observer peer and prints
every APDU flowing between the two phones in real time.

Protocol (verified from the official client source):
  TCP (optionally TLS), frames of:
      [4-byte big-endian length][1-byte session number][protobuf ServerData]
  ServerData.opcode : OP_SYN=0? no -> SYN=1, ACK=2, FIN=3, PSH=0
  ServerData.data   : for PSH, an NFCData message:
      data_source (READER=0 / CARD=1), data_type (INITIAL=0/CONTINUATION=1),
      timestamp (unix ms), raw APDU bytes.

Usage:
    python nfcgate_monitor.py <host> [--port 5566] [--tls cert.crt] [--insecure]
"""

import argparse
import socket
import ssl
import struct
import sys
import time

# ---------------------------------------------------------------- protobuf --
def _read_varint(buf, i):
    result = 0
    shift = 0
    while True:
        b = buf[i]; i += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, i
        shift += 7

def parse_fields(buf):
    """Minimal protobuf wire-format parser: returns {field_no: [values]}."""
    fields = {}
    i = 0
    while i < len(buf):
        tag, i = _read_varint(buf, i)
        field_no, wt = tag >> 3, tag & 7
        if wt == 0:                      # varint
            val, i = _read_varint(buf, i)
        elif wt == 2:                    # length-delimited
            ln, i = _read_varint(buf, i)
            val = buf[i:i + ln]; i += ln
        else:
            raise ValueError(f"unsupported wire type {wt} for field {field_no}")
        fields.setdefault(field_no, []).append(val)
    return fields

OP_PSH, OP_SYN, OP_ACK, OP_FIN = 0, 1, 2, 3
OP_NAMES = {0: "PSH", 1: "SYN", 2: "ACK", 3: "FIN"}
SRC_NAMES = {0: "READER", 1: "CARD"}

def encode_server_data(opcode, data=b""):
    """Serialize ServerData{opcode=field1 varint, data=field2 bytes}."""
    out = b"\x08" + opcode.to_bytes(1, "big")   # field 1, wire type 0
    if data:
        out += b"\x12" + len(data).to_bytes(1, "big") + data  # field 2, wt 2
    return out

# ------------------------------------------------------------- APDU helpers --
INS_NAMES = {
    0x00: "SELECT",       0xA4: "SELECT (P1)", 0xB0: "READ BINARY",
    0xCA: "GET DATA",     0x88: "GENERATE GENERAL PURPOSE",
    0xAE: "EXTERNAL AUTHENTICATE", 0x10: "INTERNAL AUTHENTICATE",
    0x20: "VERIFY CHALLENGE (PIN)", 0x34: "PSE",        0xC0: "GET RESPONSE",
}

def describe_apdu(apdu):
    if len(apdu) < 4:
        return "(short APDU)"
    ins = apdu[1]
    name = INS_NAMES.get(ins, "")
    return f"INS=0x{ins:02X}" + (f" {name}" if name else "")

# ------------------------------------------------------------------ network --
def frame_write(sock, session, payload):
    sock.sendall(struct.pack(">I", len(payload)) + bytes([session]) + payload)

def frame_read(sock):
    header = _recv_exact(sock, 4)
    (length,) = struct.unpack(">I", header)
    if length > 100 * 1024 * 1024:
        raise ConnectionError(f"invalid protocol length prefix: {length}")
    rest = _recv_exact(sock, length + 1)
    session = rest[0]
    return session, rest[1:]

def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("server closed the connection")
        buf += chunk
    return buf

# --------------------------------------------------------------------- main --
def main():
    ap = argparse.ArgumentParser(description="NFCGate bridge live monitor")
    ap.add_argument("host", help="VPS hostname or IP")
    ap.add_argument("--port", type=int, default=5566)
    ap.add_argument("--session", type=int, default=0,
                    help="session number to observe (default 0)")
    ap.add_argument("--tls", metavar="CERT",
                    help="path to server cert; enables TLS")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS certificate verification")
    args = ap.parse_args()

    raw = socket.create_connection((args.host, args.port), timeout=10)
    sock = raw
    if args.tls:
        ctx = ssl.create_default_context(cafile=args.tls)
        if args.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(raw, server_hostname=args.host)

    print(f"[*] Connected to {args.host}:{args.port}"
          f"{' (TLS)' if args.tls else ' (plain TCP)'}")
    print("[*] Joining session " + str(args.session) + " as observer...\n")

    frame_write(sock, args.session, encode_server_data(OP_SYN))
    print("[*] Handshake sent. Waiting for traffic between the phones\n"
          + "=" * 62)

    stats = {"reader": 0, "card": 0}
    try:
        while True:
            session, payload = frame_read(sock)
            fields = parse_fields(payload)
            opcode = (fields.get(1) or [OP_PSH])[0]
            name = OP_NAMES.get(opcode, f"OP{opcode}")

            if name == "ACK":
                print(f"[~] {time.strftime('%H:%M:%S')}  ACK from session "
                      f"{session} (peer confirmed)")
                continue
            if name in ("SYN", "FIN"):
                print(f"[~] {time.strftime('%H:%M:%S')}  {name} on session "
                      f"{session}")
                if name == "ACK":
                    pass
                # answer SYN like the official client does (harmless)
                if name == "SYN":
                    frame_write(sock, args.session, encode_server_data(OP_ACK))
                continue

            # PSH -> parse inner NFCData
            data = (fields.get(2) or [b""])[0]
            nf = parse_fields(data) if data else {}
            src = SRC_NAMES.get((nf.get(1) or [None])[0], "?")
            dt  = (nf.get(2) or [0])[0]
            ts  = (nf.get(4) or [0])[0] / 1000.0
            apdu = (nf.get(3) or [b""])[0]

            now = time.strftime("%H:%M:%S")
            if src == "READER":
                stats["reader"] += 1
                arrow, color = "\u2192 CARD", "\x1b[36m"   # cyan
            else:
                stats["card"] += 1
                arrow, color = "\u2190 READER", "\x1b[35m"  # magenta

            hexdump = apdu.hex().upper()
            print(f"{color}[{now}] {src:>6} {arrow}"
                  f"  ({len(apdu):>3} B)  {describe_apdu(apdu)}")
            # wrap hex at 48 chars
            for j in range(0, len(hexdump), 48):
                print(f"{color}{' ' * 12}{hexdump[j:j+48]}")
            sys.stdout.write("\x1b[0m\n")
    except (ConnectionError, EOFError) as e:
        print(f"\n[*] Disconnected: {e}")
    except KeyboardInterrupt:
        print("\n[*] Stopping...")
    finally:
        try:
            frame_write(sock, args.session, encode_server_data(OP_FIN))
        except OSError:
            pass
        sock.close()
        print(f"[*] Totals: {stats['reader']} APDUs reader->card, "
              f"{stats['card']} card->reader")

if __name__ == "__main__":
    main()