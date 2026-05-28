# GRFICSv3 Apple Silicon Mac Setup

This guide sets up GRFICSv3 on an Apple Silicon MacBook using Homebrew, Docker CLI, Docker Compose, and Colima. It matches the setup used for this fork, including the larger Colima VM needed for the Wazuh SIEM profile.

Use this when you want the MacBook to act as the lab server and open GRFICSv3 from the Mac itself or from other computers on the same Wi-Fi/LAN.

## What This Sets Up

- Homebrew packages: `docker`, `docker-compose`, and `colima`
- Docker CLI Compose plugin path for Homebrew
- Colima Docker VM with `4` CPUs and `8` GB memory
- GRFICSv3 with the SIEM profile by default
- Browser access for Simulation, Kali, Engineering Workstation, Caldera, Wazuh, HMI, and PLC

## One-Command Setup

From the repo root:

```bash
python3 scripts/setup_apple_silicon_mac.py
```

The script will:

1. Confirm the machine is Apple Silicon macOS.
2. Check Xcode Command Line Tools.
3. Check Homebrew.
4. Install `docker`, `docker-compose`, and `colima` if needed.
5. Configure Docker Compose for the Homebrew plugin path.
6. Start Colima with `--cpu 4 --memory 8`.
7. Start GRFICSv3 with Wazuh:

```bash
docker compose --profile siem up -d
```

## If Homebrew Is Missing

Install Homebrew from [brew.sh](https://brew.sh), or let the setup script run the official installer:

```bash
python3 scripts/setup_apple_silicon_mac.py --install-homebrew
```

If Xcode Command Line Tools are missing, run:

```bash
xcode-select --install
```

Finish the macOS installer prompt, then re-run the setup script.

## Start Without Wazuh

For a lighter startup:

```bash
python3 scripts/setup_apple_silicon_mac.py --no-siem
```

That runs:

```bash
docker compose up -d
```

## Rebuild Kali and EWS

Use this after changing the noVNC workstation code:

```bash
python3 scripts/setup_apple_silicon_mac.py --rebuild-workstations
```

## Stop the Lab

Stop the containers:

```bash
python3 scripts/setup_apple_silicon_mac.py --stop
```

Stop containers and Colima:

```bash
python3 scripts/setup_apple_silicon_mac.py --stop --stop-colima
```

## Manual Commands

If you prefer to run everything manually:

```bash
brew install docker docker-compose colima
mkdir -p ~/.docker
```

Create or update `~/.docker/config.json` so it includes:

```json
{
  "cliPluginsExtraDirs": [
    "/opt/homebrew/lib/docker/cli-plugins"
  ]
}
```

Then run:

```bash
docker context use colima
colima start --cpu 4 --memory 8
docker compose --profile siem up -d
docker compose --profile siem ps
```

If Colima says it is running but Docker cannot connect, restart Colima:

```bash
colima stop
colima start --cpu 4 --memory 8
docker context use colima
```

## Browser URLs

On the Mac:

| Service | URL |
| --- | --- |
| Simulation | `http://localhost` |
| Kali attacker | `http://localhost:6088` |
| Engineering Workstation | `http://localhost:6080` |
| Caldera | `http://localhost:8888` |
| Wazuh | `http://localhost:5601` |
| HMI | `http://localhost:6081` |
| PLC | `http://localhost:8080` |

From another computer on the same Wi-Fi/LAN, replace `localhost` with the Mac's IP address.

Find the Mac IP:

```bash
ipconfig getifaddr en0
```

Example:

```text
http://192.168.36.178:6088
http://192.168.36.178:6080
http://192.168.36.178:5601
```

## Logins

| Service | Login |
| --- | --- |
| Kali | `kali / kali` |
| Caldera | `red / fortiphyd-red` |
| Wazuh | `admin / admin` |
| HMI | `admin / admin` |
| PLC | `openplc / openplc` |

## Wazuh Agent Check

After startup, confirm agents:

```bash
docker exec wazuh /var/ossec/bin/agent_control -l
```

You want these agents to be active:

```text
scadalts
router
EWS
```

If one is disconnected immediately after boot, wait a minute and check again. If `scadalts` is still disconnected, restart the HMI agent:

```bash
docker exec HMI /var/ossec/bin/wazuh-control restart
docker exec wazuh /var/ossec/bin/agent_control -l
```

## Security Note

Do not expose these ports directly to the public internet. This lab includes attacker tooling, default credentials, PLC/HMI interfaces, Caldera, and Wazuh. For remote access outside your LAN, use a private overlay network such as Tailscale and use the Mac's private Tailscale IP with the same ports.

