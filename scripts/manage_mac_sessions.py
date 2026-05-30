#!/usr/bin/env python3
"""Manage multiple isolated GRFICSv3 sessions on one Apple Silicon Mac."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_DIR = REPO_ROOT / ".grfics_sessions"
CALDERA_FACT = REPO_ROOT / "caldera" / "0033b644-a615-4eff-bcf3-178e9b17adc3.yml"
CALDERA_FACT_TARGET = (
    "/usr/src/app/plugins/modbus/data/sources/"
    "0033b644-a615-4eff-bcf3-178e9b17adc3.yml"
)
PLC_MBCONFIG = REPO_ROOT / "plc" / "mbconfig.cfg"
UNITY_BUILD_DIR = REPO_ROOT / "simulation" / "web_visualization" / "Build"

BASE_PORTS = {
    "simulation": 80,
    "ews": 6080,
    "hmi": 6081,
    "kali": 6088,
    "plc": 8080,
    "caldera": 8888,
    "wazuh": 5601,
    "wazuh_agent_enroll": 1514,
    "wazuh_agent_comm": 1515,
    "wazuh_api": 55000,
    "wireguard": 51820,
}

PORT_KEYS = tuple(BASE_PORTS)

SERVICE_SUFFIXES = {
    "simulation": "simulation",
    "plc": "plc",
    "ews": "EWS",
    "hmi": "HMI",
    "kali": "kali",
    "router": "router",
    "caldera": "caldera",
    "wazuh": "wazuh",
}

REBUILD_SERVICES = ["simulation", "kali", "ews", "hmi", "router"]


def log(message: str) -> None:
    print(f"[grfics-sessions] {message}", flush=True)


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(command))
    return subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def session_name(index: int) -> str:
    return f"grfics{index}"


def port_for(index: int, key: str) -> int:
    if key == "simulation" and index > 1:
        return 12080 + ((index - 2) * 10000)
    if key == "wireguard":
        return 51820 + (((index - 1) % 2) * 10000) + ((index - 1) // 2)
    if key == "wazuh_api":
        return 55000 + (((index - 1) % 2) * 10000) + ((index - 1) // 2)
    return BASE_PORTS[key] + ((index - 1) * 10000)


def validate_session_ports(count: int) -> None:
    seen: dict[int, str] = {}
    errors: list[str] = []

    for index in range(1, count + 1):
        for key in PORT_KEYS:
            port = port_for(index, key)
            label = f"{session_name(index)} {key}"
            if port < 1 or port > 65535:
                errors.append(f"{label} maps to invalid port {port}")
            elif port in seen:
                errors.append(f"{label} collides with {seen[port]} on port {port}")
            else:
                seen[port] = label

    if errors:
        raise SystemExit("Invalid multi-session port plan:\n  " + "\n  ".join(errors))


def network_values(index: int) -> dict[str, str]:
    if index == 1:
        dmz_octet = 90
        ics_octet = 95
    else:
        dmz_octet = 90 + index - 1
        ics_octet = 95 + index - 1

    dmz_prefix = f"192.168.{dmz_octet}"
    ics_prefix = f"192.168.{ics_octet}"
    return {
        "dmz_prefix": dmz_prefix,
        "ics_prefix": ics_prefix,
        "dmz_subnet": f"{dmz_prefix}.0/24",
        "ics_subnet": f"{ics_prefix}.0/24",
        "dmz_gateway": f"{dmz_prefix}.1",
        "ics_gateway": f"{ics_prefix}.1",
        "router_dmz": f"{dmz_prefix}.200",
        "router_ics": f"{ics_prefix}.200",
        "wazuh": f"{dmz_prefix}.20",
        "kali": f"{dmz_prefix}.6",
        "hmi": f"{dmz_prefix}.107",
        "caldera": f"{dmz_prefix}.250",
        "plc": f"{ics_prefix}.2",
        "ews": f"{ics_prefix}.5",
        "simulation": f"{ics_prefix}.45",
        "feed1": f"{ics_prefix}.10",
        "feed2": f"{ics_prefix}.11",
        "purge": f"{ics_prefix}.12",
        "product": f"{ics_prefix}.13",
        "tank": f"{ics_prefix}.14",
        "analyzer": f"{ics_prefix}.15",
    }


def env_block(values: dict[str, str]) -> str:
    pairs = {
        "ICS_PREFIX": values["ics_prefix"],
        "DMZ_PREFIX": values["dmz_prefix"],
        "ICS_SUBNET": values["ics_subnet"],
        "DMZ_SUBNET": values["dmz_subnet"],
        "ROUTER_ICS_IP": values["router_ics"],
        "ROUTER_DMZ_IP": values["router_dmz"],
        "WAZUH_MANAGER_IP": values["wazuh"],
    }
    return "\n".join(f"      - {key}={value}" for key, value in pairs.items())


def indented_env(values: dict[str, str]) -> str:
    return env_block(values)


def write_caldera_fact(index: int, values: dict[str, str]) -> Path:
    session_path = SESSION_DIR / session_name(index) / "caldera"
    session_path.mkdir(parents=True, exist_ok=True)
    fact_path = session_path / CALDERA_FACT.name
    text = CALDERA_FACT.read_text()
    text = text.replace("192.168.95.10", values["feed1"])
    fact_path.write_text(text)
    return fact_path


def write_plc_mbconfig(index: int, values: dict[str, str]) -> Path:
    session_path = SESSION_DIR / session_name(index) / "plc"
    session_path.mkdir(parents=True, exist_ok=True)
    config_path = session_path / PLC_MBCONFIG.name
    replacements = {
        "192.168.95.10": values["feed1"],
        "192.168.95.11": values["feed2"],
        "192.168.95.12": values["purge"],
        "192.168.95.13": values["product"],
        "192.168.95.14": values["tank"],
        "192.168.95.15": values["analyzer"],
    }
    text = PLC_MBCONFIG.read_text()
    for old, new in replacements.items():
        text = text.replace(old, new)
    config_path.write_text(text)
    return config_path


def write_plc_start_script(index: int, values: dict[str, str]) -> Path:
    session_path = SESSION_DIR / session_name(index) / "plc"
    session_path.mkdir(parents=True, exist_ok=True)
    script_path = session_path / "start_openplc.sh"
    script_path.write_text(
        f"""#!/bin/bash
if [ -d "/docker_persistent" ]; then
    mkdir -p /docker_persistent/st_files
    cp -vn /workdir/webserver/dnp3_default.cfg /docker_persistent/dnp3.cfg
    cp -vn /workdir/webserver/openplc_default.db /docker_persistent/openplc.db
    cp -vn /workdir/webserver/active_program_default /docker_persistent/active_program
    cp -vn /workdir/webserver/mbconfig_default.cfg /docker_persistent/mbconfig.cfg
    cp -vnr /workdir/webserver/st_files_default/* /docker_persistent/st_files/ || true
fi
cd /workdir/webserver
route add -net {values['dmz_subnet']} gw {values['router_ics']} || true
/workdir/.venv/bin/python3 webserver.py
"""
    )
    script_path.chmod(0o755)
    return script_path


def generate_override(index: int) -> Path:
    name = session_name(index)
    values = network_values(index)
    fact_path = write_caldera_fact(index, values)
    mbconfig_path = write_plc_mbconfig(index, values)
    plc_start_path = write_plc_start_script(index, values)
    session_path = SESSION_DIR / name
    session_path.mkdir(parents=True, exist_ok=True)
    compose_path = session_path / "docker-compose.yml"
    common_env = indented_env(values)

    compose_path.write_text(
        f"""services:
  simulation:
    container_name: {name}_simulation
    hostname: simulation
    image: fortiphyd/grfics-simulation
    build: {REPO_ROOT / "simulation"}
    cap_add:
      - NET_ADMIN
    ports:
      - "{port_for(index, 'simulation')}:80"
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "55555"]
      interval: 5s
      retries: 5
    dns:
      - {values['router_ics']}
    environment:
{common_env}
    networks:
      a-grfics-admin:
        priority: 10
      b-ics-net:
        ipv4_address: {values['simulation']}
        priority: 100
    volumes:
      - {REPO_ROOT / "simulation" / "entrypoint.sh"}:/entrypoint.sh:ro
      - {REPO_ROOT / "simulation" / "web_visualization" / "index.html"}:/var/www/html/index.html:ro

  plc:
    container_name: {name}_plc
    hostname: plc
    image: fortiphyd/grfics-plc
    build: {REPO_ROOT / "plc"}
    cap_add:
      - NET_ADMIN
    ports:
      - "{port_for(index, 'plc')}:8080"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    dns:
      - {values['router_ics']}
    environment:
{common_env}
    networks:
      a-grfics-admin:
        priority: 10
      b-ics-net:
        ipv4_address: {values['plc']}
        priority: 100
    volumes:
      - plc_volume:/docker_persistent
      - {mbconfig_path}:/docker_persistent/mbconfig.cfg
      - {plc_start_path}:/workdir/start_openplc.sh:ro

  ews:
    container_name: {name}_EWS
    hostname: EWS
    image: fortiphyd/grfics-workstation
    build: {REPO_ROOT / "workstation"}
    cap_add:
      - NET_ADMIN
    ports:
      - "{port_for(index, 'ews')}:6080"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:6080/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    dns:
      - {values['router_ics']}
    environment:
{common_env}
    networks:
      a-grfics-admin:
        priority: 10
      b-ics-net:
        ipv4_address: {values['ews']}
        priority: 100
    volumes:
      - {REPO_ROOT / "workstation" / "start.sh"}:/usr/local/bin/start.sh:ro

  hmi:
    container_name: {name}_HMI
    image: fortiphyd/grfics-scadalts
    build: {REPO_ROOT / "scadalts"}
    cap_add:
      - NET_ADMIN
    ports:
      - "{port_for(index, 'hmi')}:8080"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 60s
    dns:
      - {values['router_dmz']}
    environment:
{common_env}
    networks:
      a-grfics-admin:
        priority: 10
      c-dmz-net:
        ipv4_address: {values['hmi']}
        priority: 100
    volumes:
      - {REPO_ROOT / "scadalts" / "init.sh"}:/init.sh:ro
      - scadalts_db:/var/lib/mysql

  kali:
    container_name: {name}_kali
    hostname: kali
    image: fortiphyd/grfics-attacker
    build: {REPO_ROOT / "attacker"}
    cap_add:
      - NET_ADMIN
    ports:
      - "{port_for(index, 'kali')}:6080"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:6080/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    dns:
      - {values['router_dmz']}
    environment:
{common_env}
    networks:
      a-grfics-admin:
        priority: 10
      c-dmz-net:
        ipv4_address: {values['kali']}
        priority: 100
    sysctls:
      net.ipv4.conf.default.arp_announce: 2
      net.ipv4.conf.all.arp_announce: 2

  router:
    container_name: {name}_router
    hostname: router
    image: fortiphyd/grfics-router
    build: {REPO_ROOT / "router"}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "bash", "-c", "ip route | grep -q {values['ics_subnet']} || exit 1"]
      interval: 5s
      retries: 5
    cap_add:
      - NET_ADMIN
      - NET_RAW
    sysctls:
      net.ipv4.ip_forward: '1'
    environment:
      - FWUI_SECRET_KEY=some-long-secret-you-generate-{name}
{common_env}
    ports:
      - "{port_for(index, 'wireguard')}:51820/udp"
    volumes:
      - router_config:/etc/firewall
      - {REPO_ROOT / "router" / "app.py"}:/opt/fwui/app.py:ro
      - {REPO_ROOT / "router" / "dashboard.html"}:/opt/fwui/templates/dashboard.html:ro
      - {REPO_ROOT / "router" / "firewall.html"}:/opt/fwui/templates/firewall.html:ro
      - {REPO_ROOT / "router" / "dns.html"}:/opt/fwui/templates/dns.html:ro
      - {REPO_ROOT / "router" / "diagnostics.html"}:/opt/fwui/templates/diagnostics.html:ro
    networks:
      a-grfics-admin:
      b-ics-net:
        ipv4_address: {values['router_ics']}
      c-dmz-net:
        ipv4_address: {values['router_dmz']}

  caldera:
    container_name: {name}_caldera
    hostname: caldera
    image: fortiphyd/grfics-caldera
    build: {REPO_ROOT / "caldera"}
    restart: unless-stopped
    ports:
      - "{port_for(index, 'caldera')}:8888"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8888/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    dns:
      - {values['router_dmz']}
    environment:
{common_env}
    volumes:
      - {fact_path}:{CALDERA_FACT_TARGET}:ro
    networks:
      a-grfics-admin:
        priority: 10
      c-dmz-net:
        ipv4_address: {values['caldera']}
        priority: 100

  wazuh:
    profiles: [siem]
    container_name: {name}_wazuh
    hostname: wazuh
    image: fortiphyd/grfics-wazuh
    build: {REPO_ROOT / "wazuh"}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:5601/"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 180s
    ports:
      - "{port_for(index, 'wazuh_agent_enroll')}:1514"
      - "{port_for(index, 'wazuh_agent_comm')}:1515"
      - "{port_for(index, 'wazuh_api')}:55000"
      - "{port_for(index, 'wazuh')}:5601"
    dns:
      - {values['router_dmz']}
    environment:
{common_env}
    cap_add:
      - NET_ADMIN
    volumes:
      - {REPO_ROOT / "wazuh" / "entrypoint.sh"}:/entrypoint.sh:ro
      - wazuh_manager_data:/var/ossec
      - wazuh_indexer_data:/var/lib/wazuh-indexer
    networks:
      a-grfics-admin:
        priority: 10
      c-dmz-net:
        ipv4_address: {values['wazuh']}
        priority: 100

networks:
  b-ics-net:
    driver: macvlan
    driver_opts:
      parent: eth0
    ipam:
      config:
        - subnet: {values['ics_subnet']}
          gateway: {values['ics_gateway']}

  c-dmz-net:
    driver: macvlan
    driver_opts:
      parent: eth0
    ipam:
      config:
        - subnet: {values['dmz_subnet']}
          gateway: {values['dmz_gateway']}

  a-grfics-admin:
    driver: bridge

volumes:
  scadalts_db:
    name: {name}_scadalts_db
  plc_volume:
    name: {name}_plc_volume
  router_config:
    name: {name}_router_config
  wazuh_manager_data:
    name: {name}_wazuh_manager_data
  wazuh_indexer_data:
    name: {name}_wazuh_indexer_data
""",
    )
    return compose_path


def compose_base(index: int, *, with_siem: bool = True) -> list[str]:
    compose_file = generate_override(index)
    command = [
        "docker",
        "compose",
        "-p",
        session_name(index),
        "-f",
        str(compose_file),
    ]
    if with_siem:
        command += ["--profile", "siem"]
    return command


def container_name(index: int, service: str) -> str:
    return f"{session_name(index)}_{SERVICE_SUFFIXES[service]}"


def docker_exec(index: int, service: str, script: str, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container_name(index, service), "sh", "-lc", script], check=check)


def docker_available() -> bool:
    result = run(["docker", "info"], check=False, capture=True)
    return result.returncode == 0


def flush_neighbor_tables(index: int) -> None:
    for service in ("simulation", "plc", "ews", "hmi", "kali", "router"):
        log(f"Clearing neighbor table in {container_name(index, service)}.")
        docker_exec(
            index,
            service,
            "ip neigh flush all 2>/dev/null || true; "
            "arp -d -a 2>/dev/null || true; "
            "ip -s neigh show 2>/dev/null || arp -n 2>/dev/null || true",
        )


def stop_spoofing_tools(index: int) -> None:
    patterns = "arpspoof|bettercap|ettercap|mitmf|dsniff|netwox|scapy|python.*arp"
    log(f"Stopping ARP/MITM tools in {container_name(index, 'kali')}.")
    docker_exec(
        index,
        "kali",
        f"pkill -f '{patterns}' 2>/dev/null || true; "
        f"ps aux | grep -Ei '{patterns}' | grep -v grep || true",
    )


def restore_session_routes(index: int) -> None:
    values = network_values(index)
    commands = {
        "hmi": f"ip route replace {values['ics_subnet']} via {values['router_dmz']} 2>/dev/null || "
        f"route add -net {values['ics_subnet']} gw {values['router_dmz']} || true",
        "kali": f"ip route replace {values['ics_subnet']} via {values['router_dmz']} 2>/dev/null || "
        f"route add -net {values['ics_subnet']} gw {values['router_dmz']} || true",
        "ews": f"ip route replace {values['dmz_subnet']} via {values['router_ics']} 2>/dev/null || "
        f"route add -net {values['dmz_subnet']} gw {values['router_ics']} || true",
        "simulation": f"ip route replace {values['dmz_subnet']} via {values['router_ics']} 2>/dev/null || "
        f"route add -net {values['dmz_subnet']} gw {values['router_ics']} || true",
        "plc": f"ip route replace {values['dmz_subnet']} via {values['router_ics']} 2>/dev/null || "
        f"route add -net {values['dmz_subnet']} gw {values['router_ics']} || true",
    }
    for service, command in commands.items():
        log(f"Restoring routes in {container_name(index, service)}.")
        docker_exec(index, service, f"{command}; ip route show 2>/dev/null || route -n 2>/dev/null || true")


def verify_session_modbus(index: int) -> None:
    values = network_values(index)
    hmi_check = (
        f"for port in 502 8080; do "
        f"if timeout 5 bash -c '</dev/tcp/{values['plc']}/'$port 2>/dev/null; then "
        f"echo 'HMI -> PLC:'$port' ok'; "
        f"else echo 'HMI -> PLC:'$port' fail'; fi; "
        f"done"
    )
    plc_check = (
        "for last in 10 11 12 13 14 15; do "
        f"host={values['ics_prefix']}.$last; "
        "if timeout 3 bash -c '</dev/tcp/'$host'/502' 2>/dev/null; then "
        "echo \"$host:502 ok\"; "
        "else echo \"$host:502 fail\"; fi; "
        "done"
    )
    log("Checking HMI to PLC Modbus path.")
    docker_exec(index, "hmi", hmi_check)
    log("Checking PLC to simulated Modbus devices.")
    docker_exec(index, "plc", plc_check)


def reset_session_state(index: int) -> None:
    generate_override(index)
    stop_spoofing_tools(index)
    flush_neighbor_tables(index)
    restore_session_routes(index)
    verify_session_modbus(index)
    log(f"Restarting {container_name(index, 'hmi')} so Scada-LTS reconnects cleanly.")
    run(compose_base(index) + ["restart", "hmi"], check=False)
    time.sleep(20)
    status_sessions_for([index])
    verify_session_modbus(index)


def docker_volume_exists(name: str) -> bool:
    result = run(["docker", "volume", "inspect", name], check=False, capture=True)
    return result.returncode == 0


def reset_wazuh_state(index: int) -> None:
    generate_override(index)
    name = session_name(index)
    log(f"Stopping and removing Wazuh for {name}.")
    run(compose_base(index) + ["rm", "-sf", "wazuh"], check=False)
    for suffix in ("wazuh_manager_data", "wazuh_indexer_data"):
        volume = f"{name}_{suffix}"
        if docker_volume_exists(volume):
            log(f"Removing stale Wazuh volume {volume}.")
            run(["docker", "volume", "rm", volume], check=False)
    log(f"Starting fresh Wazuh for {name}.")
    run(compose_base(index) + ["up", "-d", "wazuh"], check=False)


def docker_free_gb() -> float | None:
    result = run(["colima", "ssh", "--", "df", "-k", "/var/lib/docker"], check=False, capture=True)
    if result.returncode != 0:
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    parts = re.split(r"\s+", lines[-1].strip())
    if len(parts) < 4:
        return None
    try:
        return int(parts[3]) / 1024 / 1024
    except ValueError:
        return None


def ensure_docker_space(min_free_gb: int) -> None:
    free_gb = docker_free_gb()
    if free_gb is None:
        log("Could not read Docker disk free space; continuing.")
        return
    if free_gb >= min_free_gb:
        return
    raise SystemExit(
        f"Docker has only {free_gb:.1f} GB free, but this workflow needs at least "
        f"{min_free_gb} GB free. Reset stale Wazuh data with "
        f"`python3 scripts/manage_mac_sessions.py reset-wazuh --sessions N`, "
        "expand Colima's disk, or start without SIEM using `--no-siem`."
    )


def colima_config_values() -> dict[str, int]:
    config_path = Path.home() / ".colima" / "default" / "colima.yaml"
    values: dict[str, int] = {}
    if not config_path.exists():
        return values

    for line in config_path.read_text().splitlines():
        key, _, raw_value = line.partition(":")
        if key.strip() not in {"cpu", "memory"}:
            continue
        try:
            values[key.strip()] = int(raw_value.strip().split()[0])
        except (IndexError, ValueError):
            continue
    return values


def colima_needs_resize(cpu: int, memory: int) -> bool:
    values = colima_config_values()
    return values.get("cpu", 0) < cpu or values.get("memory", 0) < memory


def ensure_colima(cpu: int, memory: int) -> None:
    run(["docker", "context", "use", "colima"], check=False)
    if docker_available() and not colima_needs_resize(cpu, memory):
        return

    if docker_available():
        log(f"Restarting Colima with at least {cpu} CPU / {memory} GB RAM for two sessions.")
        run(["colima", "stop"], check=False)

    run(["colima", "start", "--cpu", str(cpu), "--memory", str(memory)], check=False)
    run(["docker", "context", "use", "colima"], check=False)
    if docker_available():
        return

    log("Docker is still unavailable; restarting Colima once.")
    run(["colima", "stop"], check=False)
    run(["colima", "start", "--cpu", str(cpu), "--memory", str(memory)])
    run(["docker", "context", "use", "colima"], check=False)


def stop_default_stack_if_running() -> None:
    result = run(["docker", "compose", "--profile", "siem", "ps", "-q"], check=False, capture=True)
    if result.returncode == 0 and result.stdout.strip():
        log("Stopping the original single-session stack to free default ports.")
        run(["docker", "compose", "--profile", "siem", "down"], check=False)


def unity_assets_are_lfs_pointers() -> bool:
    if not UNITY_BUILD_DIR.exists():
        return False
    for path in UNITY_BUILD_DIR.glob("*.unityweb"):
        try:
            if path.read_text(errors="ignore").startswith("version https://git-lfs.github.com/spec/v1"):
                return True
        except OSError:
            continue
    return False


def ensure_lfs_assets() -> None:
    if not unity_assets_are_lfs_pointers():
        return

    result = run(["git", "lfs", "version"], check=False, capture=True)
    if result.returncode != 0:
        raise SystemExit(
            "Unity build assets are still Git LFS pointer files. Install Git LFS with "
            "`brew install git-lfs`, then run `git lfs install && git lfs pull`."
        )

    log("Unity build assets are Git LFS pointers; fetching real assets with git lfs pull.")
    run(["git", "lfs", "install"])
    run(["git", "lfs", "pull"])


def build_session_images() -> None:
    ensure_lfs_assets()
    run(["docker", "builder", "prune", "-f"], check=False)
    for service in REBUILD_SERVICES:
        run(compose_base(1) + ["build", service])


def start_sessions(count: int, skip_build: bool, cpu: int, memory: int, with_siem: bool, min_free_gb: int) -> None:
    ensure_colima(cpu, memory)
    ensure_docker_space(min_free_gb)
    stop_default_stack_if_running()
    for index in range(1, count + 1):
        generate_override(index)
    if not skip_build:
        build_session_images()
    for index in range(1, count + 1):
        run(compose_base(index, with_siem=with_siem) + ["up", "-d"])
    log("Waiting for healthchecks to settle...")
    time.sleep(30)
    status_sessions(count, with_siem)
    print_urls(count)


def stop_sessions(count: int, with_siem: bool) -> None:
    for index in range(1, count + 1):
        run(compose_base(index, with_siem=with_siem) + ["down"], check=False)


def status_sessions(count: int, with_siem: bool = True) -> None:
    for index in range(1, count + 1):
        print(f"\n=== {session_name(index)} ===")
        run(compose_base(index, with_siem=with_siem) + ["ps"], check=False)


def status_sessions_for(indexes: list[int]) -> None:
    for index in indexes:
        print(f"\n=== {session_name(index)} ===")
        run(compose_base(index) + ["ps"], check=False)


def config_sessions(count: int) -> None:
    for index in range(1, count + 1):
        run(compose_base(index) + ["config"], check=True, capture=False)


def mac_lan_ip() -> str:
    for interface in ("en0", "en1"):
        result = run(["ipconfig", "getifaddr", interface], check=False, capture=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "MAC_IP"


def print_urls(count: int) -> None:
    host = mac_lan_ip()
    print("\nUse localhost on the Mac, or replace localhost with this LAN IP from other computers:")
    print(f"  {host}\n")
    for index in range(1, count + 1):
        values = network_values(index)
        print(f"Session {index} ({session_name(index)}):")
        print(f"  Simulation:              http://localhost:{port_for(index, 'simulation')}" if index > 1 else "  Simulation:              http://localhost")
        print(f"  Kali attacker:           http://localhost:{port_for(index, 'kali')}")
        print(f"  Engineering workstation: http://localhost:{port_for(index, 'ews')}")
        print(f"  HMI:                     http://localhost:{port_for(index, 'hmi')}")
        print(f"  PLC:                     http://localhost:{port_for(index, 'plc')}")
        print(f"  Caldera:                 http://localhost:{port_for(index, 'caldera')}")
        print(f"  Wazuh:                   http://localhost:{port_for(index, 'wazuh')}")
        print(f"  Internal DMZ subnet:     {values['dmz_subnet']}")
        print(f"  Internal ICS subnet:     {values['ics_subnet']}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated GRFICSv3 sessions on one Mac.")
    parser.add_argument("action", choices=["start", "stop", "status", "config", "urls", "reset-state", "reset-wazuh"])
    parser.add_argument("--sessions", type=int, default=1, help="Number of sessions to manage.")
    parser.add_argument("--target-session", type=int, help="Single session to reset or inspect.")
    parser.add_argument("--cpu", type=int, default=8, help="Colima CPU count for multi-session use.")
    parser.add_argument("--memory", type=int, default=16, help="Colima memory in GB for multi-session use.")
    parser.add_argument("--min-free-gb", type=int, default=15, help="Minimum Docker disk free space before start.")
    parser.add_argument("--no-siem", action="store_true", help="Do not start or manage Wazuh/SIEM containers.")
    parser.add_argument("--skip-build", action="store_true", help="Skip rebuilding local session-aware images.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(REPO_ROOT)
    if args.sessions < 1:
        raise SystemExit("--sessions must be at least 1")
    validate_session_ports(args.sessions)
    if args.target_session is not None and not 1 <= args.target_session <= args.sessions:
        raise SystemExit("--target-session must be between 1 and --sessions")
    if args.sessions > 2:
        log("WARNING: this Mac workflow is tuned for 2 sessions. More may be slow.")

    with_siem = not args.no_siem

    if args.action == "start":
        start_sessions(args.sessions, args.skip_build, args.cpu, args.memory, with_siem, args.min_free_gb)
    elif args.action == "stop":
        stop_sessions(args.sessions, with_siem)
    elif args.action == "status":
        status_sessions(args.sessions, with_siem)
    elif args.action == "config":
        config_sessions(args.sessions)
    elif args.action == "urls":
        for index in range(1, args.sessions + 1):
            generate_override(index)
        print_urls(args.sessions)
    elif args.action == "reset-state":
        if args.target_session is None:
            raise SystemExit("reset-state requires --target-session, e.g. --target-session 4")
        reset_session_state(args.target_session)
    elif args.action == "reset-wazuh":
        indexes = [args.target_session] if args.target_session is not None else list(range(1, args.sessions + 1))
        for index in indexes:
            reset_wazuh_state(index)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed with exit code {exc.returncode}: {' '.join(exc.cmd)}")
        raise SystemExit(exc.returncode)
