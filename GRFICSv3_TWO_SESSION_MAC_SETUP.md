# GRFICSv3 Two-Session Mac Setup

This guide runs two isolated GRFICSv3 lab sessions on one Apple Silicon MacBook.

Each session has its own containers, Docker networks, volumes, browser ports, Wazuh, Caldera, Kali, EWS, HMI, PLC, router, and simulation.

## Capacity Recommendation

Use this on a 24 GB Apple Silicon MacBook or better.

Recommended Colima VM:

```bash
colima stop
colima start --cpu 8 --memory 16
```

The session manager starts Colima with those values if Docker is not already available.

## Start Two Sessions

From the repo root:

```bash
python3 scripts/manage_mac_sessions.py start
```

The first run rebuilds the session-aware images for:

- `simulation`
- `kali`
- `ews`
- `hmi`
- `router`

If the Unity game files are still Git LFS pointers, the manager will run `git lfs pull` before building. If Git LFS is missing, install it:

```bash
brew install git-lfs
git lfs install
git lfs pull
```

Later starts can skip rebuilds:

```bash
python3 scripts/manage_mac_sessions.py start --skip-build
```

## URL Layout

Session 1 keeps the normal ports:

| View | URL on Mac |
| --- | --- |
| Simulation | `http://localhost` |
| Kali | `http://localhost:6088` |
| Engineering Workstation | `http://localhost:6080` |
| HMI | `http://localhost:6081` |
| PLC | `http://localhost:8080` |
| Caldera | `http://localhost:8888` |
| Wazuh | `http://localhost:5601` |

Session 2 uses a `+10000` port offset:

| View | URL on Mac |
| --- | --- |
| Simulation | `http://localhost:10080` |
| Kali | `http://localhost:16088` |
| Engineering Workstation | `http://localhost:16080` |
| HMI | `http://localhost:16081` |
| PLC | `http://localhost:18080` |
| Caldera | `http://localhost:18888` |
| Wazuh | `http://localhost:15601` |

From another computer on the same network, replace `localhost` with the Mac's LAN IP.

Find the Mac IP:

```bash
ipconfig getifaddr en0
```

Example:

```text
http://192.168.36.178:6088
http://192.168.36.178:16088
```

## Internal Network Layout

Session 1:

| Network | Subnet |
| --- | --- |
| DMZ | `192.168.90.0/24` |
| ICS | `192.168.95.0/24` |

Session 2:

| Network | Subnet |
| --- | --- |
| DMZ | `192.168.91.0/24` |
| ICS | `192.168.96.0/24` |

That means session 2 commands use session 2 IPs. For example:

```bash
nmap -sT -sV -p 502 192.168.96.10-15
```

Feed 1 in session 2 is:

```text
192.168.96.10
```

## Status

```bash
python3 scripts/manage_mac_sessions.py status
```

## Print URLs

```bash
python3 scripts/manage_mac_sessions.py urls
```

## Validate Compose Files

```bash
python3 scripts/manage_mac_sessions.py config
```

## Stop Both Sessions

```bash
python3 scripts/manage_mac_sessions.py stop
```

## Notes for Students

Do not mix session 1 and session 2 URLs or IPs.

For a class setup, assign each team a full session:

| Team | Simulation | Kali | Wazuh |
| --- | --- | --- | --- |
| Team 1 | `http://MAC_IP` | `http://MAC_IP:6088` | `http://MAC_IP:5601` |
| Team 2 | `http://MAC_IP:10080` | `http://MAC_IP:16088` | `http://MAC_IP:15601` |

## Security Note

Keep this on a trusted LAN or private overlay network such as Tailscale. Do not forward these ports to the public internet.
