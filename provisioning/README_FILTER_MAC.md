# MAC Filter Provisioning — lock CSI onto ONE transmitter

## Why
The CSI nodes capture in promiscuous mode with **no MAC filter** (`filter_mac_set=0`).
Every CSI frame comes from a different ambient WiFi transmitter → RSSI swings
−34…−75 dB frame-to-frame → presence_score is noise → empty ≈ occupied.

Setting `filter_mac` to the AP BSSID locks each node onto ONE stable link
(AP → node), so frame-to-frame CSI change reflects the channel (a person),
not which transmitter sent the frame.

## Target MAC
`72:13:01:84:04:59` — BSSID of AP "lucky plaza" on channel 1 (from host `netsh`).
Encoded in the CSV as `721301840459` (hex2bin).

> If after flashing a node goes SILENT (no CSI frames reach the backend), the
> BSSID is wrong for that node. Revert by re-flashing without the `filter_mac`
> row, or try the gateway MAC `701301830457`.

## Prerequisites (on the flashing machine)
```
pip install esptool esp-idf-nvs-partition-gen
```

## Steps (do NODE 1 FIRST, verify, then NODE 2)

1. Connect node 1 via USB. Find its COM port (Device Manager / `mode`).

2. Generate the NVS binary (24 KiB partition):
```
python -m esp_idf_nvs_partition_gen generate nvs_node1.csv nvs_node1.bin 0x6000
```
(legacy fallback: `python -m nvs_partition_gen generate nvs_node1.csv nvs_node1.bin 0x6000`)

3. Flash it to the NVS partition (offset 0x9000):
```
python -m esptool --chip esp32s3 --port COM<X> --baud 460800 write_flash 0x9000 nvs_node1.bin
```

4. Reboot the node (it reboots after flashing). **Watch the serial log** — it
   should print:
```
NVS override: filter_mac=72:13:01:84:04:59
```

5. Tell the remote operator. They confirm CSI still flows
   (`/latest` shows `csi_nodes` ≥ 1 and a changing `presence_score`).
   - **CSI flows → BSSID correct.** Proceed to node 2 (`nvs_node2.csv`, same steps).
   - **CSI silent → BSSID wrong.** Stop; revert or switch target MAC.

## After both nodes
The remote operator ping-floods the nodes (steady AP→node traffic), reboots with
the room empty to recalibrate, then re-runs the empty-vs-occupied test.

## Node IDs
`nvs_node1.csv` sets node_id=1, `nvs_node2.csv` sets node_id=2. Flash the file
matching each physical board's existing ID. Flashing NVS overwrites ALL config,
so the CSVs already include the WiFi creds + target IP to preserve them.
