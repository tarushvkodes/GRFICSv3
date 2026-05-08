# GRFICSv3 Remote Browser Access

GRFICSv3 publishes browser ports on the Mac running Docker. That lets other devices on the same Wi-Fi or LAN open the lab with the Mac's IP address.

The idea is:

```text
Your Mac = GRFICS server
Other browsers/computers = clients
Different GRFICS roles = different ports
```

This lets you run the plant simulation on one screen, Kali on another computer, Wazuh on a defender laptop, and Caldera in a separate browser.

## Find the Mac IP

```bash
ipconfig getifaddr en0
```

Example:

```text
10.231.171.156
```

## Local URLs

Use these on the Mac:

| Service | URL |
| --- | --- |
| Simulation | `http://localhost` |
| Engineering Workstation | `http://localhost:6080` |
| Kali | `http://localhost:6088` |
| HMI | `http://localhost:6081` |
| PLC | `http://localhost:8080` |
| Caldera | `http://localhost:8888` |
| Wazuh | `http://localhost:5601` |

## LAN URLs

Use these from another computer on the same network, replacing `MAC_IP` with the Mac's IP:

| Service | URL |
| --- | --- |
| Simulation | `http://MAC_IP` |
| Engineering Workstation | `http://MAC_IP:6080` |
| Kali | `http://MAC_IP:6088` |
| HMI | `http://MAC_IP:6081` |
| PLC | `http://MAC_IP:8080` |
| Caldera | `http://MAC_IP:8888` |
| Wazuh | `http://MAC_IP:5601` |

## Example Multi-Computer Setup

| Device | Suggested URL |
| --- | --- |
| Projector or large display | `http://MAC_IP` |
| Attacker computer | `http://MAC_IP:6088` |
| Defender computer | `http://MAC_IP:5601` |
| Caldera operator computer | `http://MAC_IP:8888` |
| HMI/operator computer | `http://MAC_IP:6081` |
| Engineering computer | `http://MAC_IP:6080` |

## Safer Remote Access

Do not expose these services directly to the public internet. The lab includes attack tools, PLC/HMI interfaces, Caldera, Wazuh, and default credentials.

For access outside the local network, use a private overlay network such as Tailscale. Install it on the Mac and on the remote computer, then use the Mac's Tailscale IP with the same ports.
