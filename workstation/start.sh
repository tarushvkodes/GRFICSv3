#!/bin/bash
set -e

# Setup VNC password if not present
mkdir -p /home/${USERNAME}/.vnc
if [ ! -f /home/${USERNAME}/.vnc/passwd ]; then
  echo "${VNC_PASSWORD}" | x11vnc -storepasswd - /home/${USERNAME}/.vnc/passwd
  chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.vnc
fi

DMZ_SUBNET="${DMZ_SUBNET:-192.168.90.0/24}"
ROUTER_ICS_IP="${ROUTER_ICS_IP:-192.168.95.200}"
WAZUH_MANAGER_IP="${WAZUH_MANAGER_IP:-192.168.90.20}"

route add -net "$DMZ_SUBNET" gw "$ROUTER_ICS_IP" || true

if [ -f /var/ossec/etc/ossec.conf ]; then
  sed -i "s|<address>.*</address>|<address>${WAZUH_MANAGER_IP}</address>|" /var/ossec/etc/ossec.conf || true
fi

if getent hosts wazuh >/dev/null 2>&1; then
    /var/ossec/bin/wazuh-control start || true
else
    echo "[EWS] Wazuh not in DNS, skipping agent start"
fi

exec "$@"
