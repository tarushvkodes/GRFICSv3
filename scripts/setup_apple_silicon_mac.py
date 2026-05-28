#!/usr/bin/env python3
"""Set up and start GRFICSv3 on Apple Silicon macOS with Colima."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BREW_COMPOSE_PLUGIN_DIR = "/opt/homebrew/lib/docker/cli-plugins"
DEFAULT_CPU = 4
DEFAULT_MEMORY_GB = 8


def log(message: str) -> None:
    print(f"[grfics-setup] {message}", flush=True)


def run(
    command: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    cwd: Path = REPO_ROOT,
) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(command))
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def require_apple_silicon(force: bool) -> None:
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin" and machine == "arm64":
        return
    message = f"This script is intended for Apple Silicon macOS. Detected {system}/{machine}."
    if force:
        log("WARNING: " + message)
        return
    raise SystemExit(message + " Re-run with --force to continue anyway.")


def ensure_xcode_tools() -> None:
    result = run(["xcode-select", "-p"], check=False, capture=True)
    if result.returncode == 0:
        return
    log("Xcode Command Line Tools are missing.")
    log("Run this once, finish the macOS prompt, then re-run this setup:")
    log("xcode-select --install")
    raise SystemExit(1)


def ensure_homebrew(install_homebrew: bool) -> None:
    if command_exists("brew"):
        return
    if not install_homebrew:
        log("Homebrew is not installed.")
        log("Install it from https://brew.sh, or re-run with --install-homebrew.")
        raise SystemExit(1)
    run(
        [
            "/bin/bash",
            "-c",
            "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)",
        ]
    )
    if not command_exists("brew"):
        raise SystemExit("Homebrew installation finished, but brew is still not on PATH.")


def brew_install(packages: list[str], skip_install: bool) -> None:
    if skip_install:
        log("Skipping Homebrew package install because --skip-install was set.")
        return
    for package in packages:
        result = run(["brew", "list", package], check=False, capture=True)
        if result.returncode == 0:
            log(f"{package} is already installed.")
            continue
        run(["brew", "install", package])


def configure_docker_cli_plugin() -> None:
    docker_dir = Path.home() / ".docker"
    config_path = docker_dir / "config.json"
    docker_dir.mkdir(parents=True, exist_ok=True)

    config: dict[str, object] = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            backup = config_path.with_suffix(".json.bak")
            config_path.replace(backup)
            log(f"Backed up invalid Docker config to {backup}")

    plugin_dirs = config.get("cliPluginsExtraDirs", [])
    if not isinstance(plugin_dirs, list):
        plugin_dirs = []
    if BREW_COMPOSE_PLUGIN_DIR not in plugin_dirs:
        plugin_dirs.append(BREW_COMPOSE_PLUGIN_DIR)
        config["cliPluginsExtraDirs"] = plugin_dirs
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        log(f"Added Compose plugin path to {config_path}")
    else:
        log("Docker Compose plugin path is already configured.")


def docker_available() -> bool:
    result = run(["docker", "info"], check=False, capture=True)
    return result.returncode == 0


def start_colima(cpu: int, memory: int, restart_if_needed: bool) -> None:
    run(["docker", "context", "use", "colima"], check=False)
    run(["colima", "start", "--cpu", str(cpu), "--memory", str(memory)], check=False)
    run(["docker", "context", "use", "colima"], check=False)

    if docker_available():
        return

    if not restart_if_needed:
        raise SystemExit("Colima started, but Docker is not reachable.")

    log("Colima is running but Docker is not reachable. Restarting Colima once.")
    run(["colima", "stop"], check=False)
    run(["colima", "start", "--cpu", str(cpu), "--memory", str(memory)])
    run(["docker", "context", "use", "colima"], check=False)

    if not docker_available():
        raise SystemExit("Docker is still not reachable after restarting Colima.")


def compose_command(with_siem: bool) -> list[str]:
    command = ["docker", "compose"]
    if with_siem:
        command += ["--profile", "siem"]
    return command


def start_grfics(with_siem: bool, rebuild: bool) -> None:
    command = compose_command(with_siem)
    if rebuild:
        run(command + ["build", "kali", "ews"])
    run(command + ["up", "-d"])


def wait_and_report(with_siem: bool) -> None:
    log("Waiting for services to warm up...")
    time.sleep(20)
    run(compose_command(with_siem) + ["ps"], check=False)
    print_urls()
    if with_siem:
        print_wazuh_agents()


def mac_lan_ip() -> str:
    for interface in ("en0", "en1"):
        result = run(["ipconfig", "getifaddr", interface], check=False, capture=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "MAC_IP"


def print_urls() -> None:
    ip = mac_lan_ip()
    print("\nLocal URLs on this Mac:")
    print("  Simulation:              http://localhost")
    print("  Kali attacker:           http://localhost:6088")
    print("  Engineering workstation: http://localhost:6080")
    print("  Caldera:                 http://localhost:8888")
    print("  Wazuh:                   http://localhost:5601")
    print("  HMI:                     http://localhost:6081")
    print("  PLC:                     http://localhost:8080")
    print("\nLAN URLs from another computer on the same network:")
    print(f"  Simulation:              http://{ip}")
    print(f"  Kali attacker:           http://{ip}:6088")
    print(f"  Engineering workstation: http://{ip}:6080")
    print(f"  Caldera:                 http://{ip}:8888")
    print(f"  Wazuh:                   http://{ip}:5601")
    print(f"  HMI:                     http://{ip}:6081")
    print(f"  PLC:                     http://{ip}:8080")
    print("\nDo not expose these ports directly to the public internet.")


def print_wazuh_agents() -> None:
    log("Checking Wazuh agents...")
    result = run(
        ["docker", "exec", "wazuh", "/var/ossec/bin/agent_control", "-l"],
        check=False,
        capture=True,
    )
    if result.stdout:
        print(result.stdout)


def stop_grfics(with_siem: bool, stop_colima: bool) -> None:
    run(compose_command(with_siem) + ["down"], check=False)
    if stop_colima:
        run(["colima", "stop"], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up and run GRFICSv3 on Apple Silicon macOS with Colima."
    )
    parser.add_argument("--cpu", type=int, default=DEFAULT_CPU, help="Colima CPU count.")
    parser.add_argument(
        "--memory",
        type=int,
        default=DEFAULT_MEMORY_GB,
        help="Colima memory in GB.",
    )
    parser.add_argument(
        "--no-siem",
        action="store_true",
        help="Start without the Wazuh SIEM profile.",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Install/configure tools but do not start GRFICSv3.",
    )
    parser.add_argument(
        "--rebuild-workstations",
        action="store_true",
        help="Rebuild Kali and EWS images before starting.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip Homebrew package installation.",
    )
    parser.add_argument(
        "--install-homebrew",
        action="store_true",
        help="Install Homebrew if brew is missing.",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop GRFICSv3 instead of starting it.",
    )
    parser.add_argument(
        "--stop-colima",
        action="store_true",
        help="With --stop, also stop Colima.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if this is not Apple Silicon macOS.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with_siem = not args.no_siem

    os.chdir(REPO_ROOT)
    require_apple_silicon(args.force)

    if args.stop:
        stop_grfics(with_siem=with_siem, stop_colima=args.stop_colima)
        return 0

    ensure_xcode_tools()
    ensure_homebrew(args.install_homebrew)
    brew_install(["docker", "docker-compose", "colima", "git-lfs"], args.skip_install)
    configure_docker_cli_plugin()
    start_colima(args.cpu, args.memory, restart_if_needed=True)

    if args.no_start:
        log("Setup complete. Skipping GRFICSv3 startup because --no-start was set.")
        return 0

    start_grfics(with_siem=with_siem, rebuild=args.rebuild_workstations)
    wait_and_report(with_siem=with_siem)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed with exit code {exc.returncode}: {' '.join(exc.cmd)}")
        raise SystemExit(exc.returncode)
