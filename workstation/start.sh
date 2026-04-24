#!/bin/bash
set -e

# Setup VNC password if not present
mkdir -p /home/${USERNAME}/.vnc
if [ ! -f /home/${USERNAME}/.vnc/passwd ]; then
  echo "${VNC_PASSWORD}" | x11vnc -storepasswd - /home/${USERNAME}/.vnc/passwd
  chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.vnc
fi

route add -net 192.168.90.0/24 gw 192.168.95.200

if getent hosts wazuh >/dev/null 2>&1; then
    /var/ossec/bin/wazuh-control start || true
else
    echo "[EWS] Wazuh not in DNS, skipping agent start"
fi

exec "$@"
