#!/bin/bash
set -e


# Optional: enable forwarding in iptables (accept by default)
iptables -P FORWARD ACCEPT

# Show interfaces (for troubleshooting)
ip -c addr
ip route show

/var/ossec/bin/wazuh-control start || true

# Keep container running and provide a shell via exec
exec "$@"
