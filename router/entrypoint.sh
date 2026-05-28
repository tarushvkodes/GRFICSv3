#!/bin/bash
set -e


# Default-deny forwarding; stateful rules applied by app.py on startup
iptables -P FORWARD DROP

# MASQUERADE LAN/DMZ traffic going to internet via Admin interface.
# RETURN rules skip intra-lab destinations so IDS/firewall sees real source IPs.
iptables -t nat -A POSTROUTING -s 192.168.95.0/24 -d 192.168.95.0/24 -j RETURN
iptables -t nat -A POSTROUTING -s 192.168.95.0/24 -d 192.168.90.0/24 -j RETURN
iptables -t nat -A POSTROUTING -s 192.168.90.0/24 -d 192.168.95.0/24 -j RETURN
iptables -t nat -A POSTROUTING -s 192.168.90.0/24 -d 192.168.90.0/24 -j RETURN
iptables -t nat -A POSTROUTING -s 192.168.95.0/24 -j MASQUERADE
iptables -t nat -A POSTROUTING -s 192.168.90.0/24 -j MASQUERADE

# Add .1 gateway aliases on LAN/DMZ interfaces so containers using .1 as their default
# gateway (set by Docker IPAM) can reach us — Docker reserves .200 for the container
# static IP so we can't use .200 as the IPAM gateway address.
for iface in $(ip -o link show | awk -F': ' '{print $2}' | cut -d@ -f1); do
    ip=$(ip -o -4 addr show dev "$iface" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
    case "$ip" in
        192.168.95.*) ip addr add 192.168.95.1/24 dev "$iface" 2>/dev/null || true ;;
        192.168.90.*) ip addr add 192.168.90.1/24 dev "$iface" 2>/dev/null || true ;;
    esac
done

# Ensure dnsmasq config files exist before supervisord starts dnsmasq
mkdir -p /etc/firewall /var/log/dnsmasq /var/log/arpmon /var/lib/arpmon
touch /etc/firewall/dns_hosts
[ -f /etc/firewall/dns_blocked.conf ] || touch /etc/firewall/dns_blocked.conf

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
