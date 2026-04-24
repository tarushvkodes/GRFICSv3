#!/bin/bash
set -e


# Optional: enable forwarding in iptables (accept by default)
iptables -P FORWARD ACCEPT

# Show interfaces (for troubleshooting)
ip -c addr
ip route show

if getent hosts wazuh >/dev/null 2>&1; then
    /var/ossec/bin/wazuh-control start || true
else
    echo "[router] Wazuh not in DNS, skipping agent start"
fi

# Keep container running and provide a shell via exec
exec "$@"
