#!/usr/bin/env python3
"""Manage multiple isolated GRFICSv3 sessions on one Apple Silicon Mac."""

from __future__ import annotations

import argparse
import os
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


def generate_override(index: int) -> Path:
    name = session_name(index)
    values = network_values(index)
    fact_path = write_caldera_fact(index, values)
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


def compose_base(index: int) -> list[str]:
    compose_file = generate_override(index)
    return [
        "docker",
        "compose",
        "-p",
        session_name(index),
        "-f",
        str(compose_file),
        "--profile",
        "siem",
    ]


def docker_available() -> bool:
    result = run(["docker", "info"], check=False, capture=True)
    return result.returncode == 0


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


def start_sessions(count: int, skip_build: bool, cpu: int, memory: int) -> None:
    ensure_colima(cpu, memory)
    stop_default_stack_if_running()
    for index in range(1, count + 1):
        generate_override(index)
    if not skip_build:
        build_session_images()
    for index in range(1, count + 1):
        run(compose_base(index) + ["up", "-d"])
    log("Waiting for healthchecks to settle...")
    time.sleep(30)
    status_sessions(count)
    print_urls(count)


def stop_sessions(count: int) -> None:
    for index in range(1, count + 1):
        run(compose_base(index) + ["down"], check=False)


def status_sessions(count: int) -> None:
    for index in range(1, count + 1):
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
    parser.add_argument("action", choices=["start", "stop", "status", "config", "urls"])
    parser.add_argument("--sessions", type=int, default=1, help="Number of sessions to manage.")
    parser.add_argument("--cpu", type=int, default=8, help="Colima CPU count for multi-session use.")
    parser.add_argument("--memory", type=int, default=16, help="Colima memory in GB for multi-session use.")
    parser.add_argument("--skip-build", action="store_true", help="Skip rebuilding local session-aware images.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(REPO_ROOT)
    if args.sessions < 1:
        raise SystemExit("--sessions must be at least 1")
    validate_session_ports(args.sessions)
    if args.sessions > 2:
        log("WARNING: this Mac workflow is tuned for 2 sessions. More may be slow.")

    if args.action == "start":
        start_sessions(args.sessions, args.skip_build, args.cpu, args.memory)
    elif args.action == "stop":
        stop_sessions(args.sessions)
    elif args.action == "status":
        status_sessions(args.sessions)
    elif args.action == "config":
        config_sessions(args.sessions)
    elif args.action == "urls":
        for index in range(1, args.sessions + 1):
            generate_override(index)
        print_urls(args.sessions)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed with exit code {exc.returncode}: {' '.join(exc.cmd)}")
        raise SystemExit(exc.returncode)
