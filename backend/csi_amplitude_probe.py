"""
csi_amplitude_probe.py
----------------------
Host-side occupancy probe that bypasses the firmware's (broken, phase-based)
presence_score. It listens for RAW CSI frames over UDP, computes per-subcarrier
AMPLITUDE = sqrt(I^2 + Q^2), and derives occupancy features from how the
amplitude fluctuates over time:

  * amp_std  : mean over active subcarriers of the temporal std of amplitude
               within a sliding window (a moving body modulates the channel ->
               higher std; an empty room with a STABLE link -> low std).
  * motion   : mean over active subcarriers of |A_t - A_{t-1}| (frame-to-frame
               amplitude change). Spikes when someone moves in the link path.

Amplitude is far more robust than the ESP32's raw CSI phase (which suffers
CFO/SFO/PBD rotations and saturates the firmware motion metric at 1.0), so this
is the right signal to test once a stable link exists (filter_mac set).

Raw CSI packet (ADR-018, from rf-scan.js / csi_collector.c):
  u32 magic=0xC5110001 @0 | u8 node_id @4 | u8 n_antennas @5 |
  u16 n_subcarriers @6 | u32 freq @8 | u32 seq @12 | i8 rssi @16 |
  i8 noise @17 | IQ bytes from offset 20 (i8 I, i8 Q per subcarrier)

Usage:
  python csi_amplitude_probe.py --duration 40 --node 1 --label EMPTY
  (run the bridge's rf-scan must be stopped first so this can bind UDP 5005)
"""

import argparse
import math
import socket
import struct
import time
from collections import deque

CSI_MAGIC = 0xC5110001
HEADER_SIZE = 20
PORT = 5005
AMP_FLOOR = 2.0       # subcarriers whose mean amplitude is below this are null/DC -> ignored


def parse_csi(buf):
    if len(buf) < HEADER_SIZE:
        return None
    if struct.unpack_from("<I", buf, 0)[0] != CSI_MAGIC:
        return None
    node_id = buf[4]
    n_ant = buf[5] or 1
    n_sc = struct.unpack_from("<H", buf, 6)[0]
    rssi = struct.unpack_from("<b", buf, 16)[0]
    iq_len = n_sc * n_ant * 2
    if len(buf) < HEADER_SIZE + iq_len or n_sc == 0:
        return None
    amps = [0.0] * n_sc
    for sc in range(n_sc):
        off = HEADER_SIZE + sc * 2          # first antenna only
        i = struct.unpack_from("<b", buf, off)[0]
        q = struct.unpack_from("<b", buf, off + 1)[0]
        amps[sc] = math.sqrt(i * i + q * q)
    return node_id, rssi, amps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=40)
    ap.add_argument("--node", type=int, default=None, help="only this node_id (default: any)")
    ap.add_argument("--window", type=float, default=3.0, help="sliding window seconds")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.settimeout(1.0)

    hist = deque()           # (t, amps[]) within window
    prev = None
    t0 = time.time()
    last_print = t0
    rssis = []
    amp_std_samples = []
    motion_samples = []
    n_frames = 0

    print(f"[{args.label}] listening UDP :{PORT} node={args.node} window={args.window}s dur={args.duration}s")
    while time.time() - t0 < args.duration:
        try:
            data, _ = s.recvfrom(4096)
        except socket.timeout:
            continue
        parsed = parse_csi(data)
        if not parsed:
            continue
        node_id, rssi, amps = parsed
        if args.node is not None and node_id != args.node:
            continue
        now = time.time()
        n_frames += 1
        rssis.append(rssi)

        # frame-to-frame motion (active subcarriers)
        if prev is not None and len(prev) == len(amps):
            diffs = [abs(a - b) for a, b in zip(amps, prev) if (a + b) / 2 > AMP_FLOOR]
            if diffs:
                motion_samples.append(sum(diffs) / len(diffs))
        prev = amps

        # sliding window temporal std
        hist.append((now, amps))
        while hist and now - hist[0][0] > args.window:
            hist.popleft()

        if now - last_print >= 1.0 and len(hist) >= 5:
            nsc = len(hist[-1][1])
            stds = []
            for sc in range(nsc):
                col = [h[1][sc] for h in hist if len(h[1]) == nsc]
                m = sum(col) / len(col)
                if m <= AMP_FLOOR:
                    continue
                var = sum((c - m) ** 2 for c in col) / len(col)
                stds.append(math.sqrt(var))
            amp_std = sum(stds) / len(stds) if stds else 0.0
            mot = motion_samples[-1] if motion_samples else 0.0
            amp_std_samples.append(amp_std)
            print(f"  fps~{len([h for h in hist if now-h[0]<=1.0])} rssi={rssi} "
                  f"amp_std={amp_std:.3f} motion={mot:.3f}")
            last_print = now

    s.close()

    def summ(name, x):
        if not x:
            print(f"  {name}: (no data)")
            return
        x2 = sorted(x)
        mean = sum(x) / len(x)
        med = x2[len(x2) // 2]
        print(f"  {name}: n={len(x)} mean={mean:.3f} median={med:.3f} "
              f"min={min(x):.3f} max={max(x):.3f}")

    print(f"--- SUMMARY [{args.label}] ---")
    print(f"  frames={n_frames} rssi mean={sum(rssis)/len(rssis):.1f}" if rssis else "  no frames")
    summ("amp_std", amp_std_samples)
    summ("motion", motion_samples)


if __name__ == "__main__":
    main()
