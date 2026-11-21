#!/usr/bin/env python3
"""End-to-end test: start mock bridge server, run nfcgate_monitor against it."""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ)
if os.name == "nt":
    env["PYTHONIOENCODING"] = "utf-8"

mock = subprocess.Popen([sys.executable, os.path.join(HERE, "_mock_server.py")],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        cwd=HERE, env=env)
time.sleep(1.5)  # let the mock bind and listen

mon = subprocess.Popen([sys.executable, os.path.join(HERE, "nfcgate_monitor.py"),
                        "127.0.0.1", "--port", "5599"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       cwd=HERE, env=env)

try:
    mon_out, _ = mon.communicate(timeout=6)
except subprocess.TimeoutExpired:
    mon.terminate()
    try:
        mon_out, _ = mon.communicate(timeout=3)
    except Exception:
        mon.kill(); mon_out = b""

# mock has an 8s socket timeout; give it a moment then stop it
time.sleep(1)
if mock.poll() is None:
    mock.terminate()
try:
    mock_out, _ = mock.communicate(timeout=3)
except Exception:
    mock.kill(); mock_out = b""

print("=" * 60)
print("MONITOR OUTPUT:")
print(mon_out.decode(errors="replace"))
print("-" * 60)
print("MOCK SERVER OUTPUT:")
print(mock_out.decode(errors="replace"))

ok = ("READER" in mon_out.decode(errors="replace") and
      "00A40400" in mon_out.decode(errors="replace").upper())
print("=" * 60)
print("RESULT:", "PASS - monitor decoded the relayed APDU correctly" if ok
      else "FAIL - expected READER + SELECT hex not found")
sys.exit(0 if ok else 1)