# GRFICSv3 Mac Installation Writeup

This repo was run on macOS using Homebrew, Docker CLI, Docker Compose, and Colima.

## Install Tools

```bash
brew install docker docker-compose colima
```

If `docker compose` is not found, add the Homebrew Compose plugin path:

```bash
mkdir -p ~/.docker
```

Create `~/.docker/config.json`:

```json
{
  "cliPluginsExtraDirs": [
    "/opt/homebrew/lib/docker/cli-plugins"
  ]
}
```

## Clone and Run

```bash
git clone https://github.com/Fortiphyd/GRFICSv3.git
cd GRFICSv3
colima start
docker compose up -d
docker compose ps
```

## Run with Wazuh SIEM

Wazuh needs more memory than the default Colima VM.

```bash
colima stop
colima start --cpu 4 --memory 8
docker compose --profile siem up -d
docker exec wazuh /var/ossec/bin/agent_control -l
```

Expected connected agents include:

```text
EWS
router
scadalts
```

## Stop

Basic lab:

```bash
docker compose down
colima stop
```

Full SIEM lab:

```bash
docker compose --profile siem down
colima stop
```

