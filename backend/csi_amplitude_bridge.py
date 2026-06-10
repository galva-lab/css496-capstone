"""
csi_amplitude_bridge.py
-----------------------
Replacement for ruview_bridge.py that derives occupancy from raw-CSI AMPLITUDE
instead of the firmware's phase-based presence_score (which saturates: motion is
pegged at 1.0 and presence swings 1..37 even in an empty room).

Why this works where the old bridge didn't:
  * filter_mac (set in NVS) locks each node onto ONE transmitter (the AP BSSID),
    so RSSI is stable (+/-1 dB) instead of swinging 40 dB across ambient sources.
  * AMPLITUDE = sqrt(I^2+Q^2) is robust; CSI phase on the ESP32 is not (CFO/SFO).
  * The occupancy feature is the temporal std of amplitude over a short window:
    a moving body modulates the channel (high std), an empty room with a stable
    link is quiet (low std).

Validated empty-vs-occupied on a single node: Cohen d=0.63, ~85% separation at
amp_std threshold ~0.93 (see docs). Combining nodes (max) widens coverage.

It listens for raw CSI (UDP :5005, magic 0xC5110001), computes amp_std per node,
maps the combined value to a presence_score on a scale the existing backend +
people_counter understands, and POSTs to /sensor-data every UPDATE_INTERVAL s so
the dashboard shows real Empty/Occupied.

Run the bridge's rf-scan must NOT be running (this binds UDP 5005).

Usage:
  python csi_amplitude_bridge.py            # nodes 1 and 5
  python csi_amplitude_bridge.py --nodes 1 5 --scale 10 --window 3
"""

import argparse
import math
import socket
import struct
import threading
import time
from collections import deque

import requests

CSI_MAGIC = 0xC5110001
HEADER_SIZE = 20
UDP_PORT = 5005
AMP_FLOOR = 2.0
BACKEND_URL = "http://127.0.0.1:8000/sensor-data"
UPDATE_INTERVAL = 2.0


def parse_csi(buf):
    if len(buf) < HEADER_SIZE or struct.unpack_from("<I", buf, 0)[0] != CSI_MAGIC:
        return None
    node_id = buf[4]
    n_ant = buf[5] or 1
    n_sc = struct.unpack_from("<H", buf, 6)[0]
    rssi = struct.unpack_from("<b", buf, 16)[0]
    iq_len = n_sc * n_ant * 2
    if n_sc == 0 or len(buf) < HEADER_SIZE + iq_len:
        return None
    amps = [0.0] * n_sc
    for sc in range(n_sc):
        off = HEADER_SIZE + sc * 2
        i = struct.unpack_from("<b", buf, off)[0]
        q = struct.unpack_from("<b", buf, off + 1)[0]
        amps[sc] = math.sqrt(i * i + q * q)
    return node_id, rssi, amps


class NodeWindow:
    """Sliding window of recent amplitude vectors for one node."""
    def __init__(self, window_s):
        self.window_s = window_s
        self.frames = deque()   # (t, amps)
        self.last_rssi = 0

    def push(self, t, rssi, amps):
        self.last_rssi = rssi
        self.frames.append((t, amps))
        while self.frames and t - self.frames[0][0] > self.window_s:
            self.frames.popleft()

    def amp_std(self):
        """Mean over active subcarriers of temporal std of amplitude."""
        if len(self.frames) < 5:
            return 0.0
        nsc = len(self.frames[-1][1])
        stds = []
        for sc in range(nsc):
            col = [f[1][sc] for f in self.frames if len(f[1]) == nsc]
            m = sum(col) / len(col)
            if m <= AMP_FLOOR:
                continue
            var = sum((c - m) ** 2 for c in col) / len(col)
            stds.append(math.sqrt(var))
        return sum(stds) / len(stds) if stds else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", type=int, nargs="+", default=[1, 5])
    ap.add_argument("--scale", type=float, default=10.0,
                    help="presence_score = EMA(combined amp_std) * scale")
    ap.add_argument("--window", type=float, default=3.0)
    ap.add_argument("--ema", type=float, default=0.3,
                    help="EMA weight on newest amp_std (lower = smoother)")
    args = ap.parse_args()

    windows = {n: NodeWindow(args.window) for n in args.nodes}
    lock = threading.Lock()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(1.0)

    def reader():
        while True:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            p = parse_csi(data)
            if not p:
                continue
            node_id, rssi, amps = p
            if node_id not in windows:
                continue
            with lock:
                windows[node_id].push(time.time(), rssi, amps)

    threading.Thread(target=reader, daemon=True).start()

    print("=" * 55)
    print("  CSI Amplitude Bridge (occupancy from amplitude std)")
    print(f"  nodes={args.nodes} scale={args.scale} window={args.window}s")
    print(f"  backend={BACKEND_URL}")
    print("=" * 55)

    ema = None
    while True:
        time.sleep(UPDATE_INTERVAL)
        with lock:
            per_node = {n: windows[n].amp_std() for n in args.nodes}
            rssis = {n: windows[n].last_rssi for n in args.nodes}
        combined = max(per_node.values()) if per_node else 0.0
        # EMA-smooth the feature so per-window noise (an empty room occasionally
        # spiking above threshold) cannot latch the backend into "Occupied".
        ema = combined if ema is None else args.ema * combined + (1 - args.ema) * ema
        presence_score = round(ema * args.scale, 2)
        payload = {
            "source": "wifi_csi",
            "presence_score": presence_score,
            "motion": combined > 0.0,
            "n_persons": 1,
            "sound_level": 0,
            "gas_level": 0,
            "rssi": rssis.get(args.nodes[0], 0),
            "csi_nodes": len(args.nodes),
            "amp_std": round(combined, 3),
        }
        try:
            requests.post(BACKEND_URL, json=payload, timeout=3)
        except requests.exceptions.ConnectionError:
            print("[csi-amp] backend not reachable")
            continue
        except Exception as e:
            print(f"[csi-amp] POST error: {e}")
            continue
        detail = " ".join(f"n{n}={per_node[n]:.2f}(rssi{rssis[n]})" for n in args.nodes)
        print(f"[csi-amp] amp_std={combined:.3f} -> presence={presence_score} | {detail}")


if __name__ == "__main__":
    main()
