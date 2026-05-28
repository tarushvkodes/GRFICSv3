#!/bin/bash
set -e

# Detect interface by IP
ICS_PREFIX="${ICS_PREFIX:-192.168.95}"
DMZ_SUBNET="${DMZ_SUBNET:-192.168.90.0/24}"
ROUTER_ICS_IP="${ROUTER_ICS_IP:-${ICS_PREFIX}.200}"
IF=$(ip -o -4 addr show | awk -v prefix="$ICS_PREFIX" '$4 ~ "^" prefix "\\." {print $2}' | head -n1)


echo "[entrypoint] Adding IP aliases to $IF manually..."

ip addr add "${ICS_PREFIX}.10/24" dev "$IF"
ip addr add "${ICS_PREFIX}.11/24" dev "$IF"
ip addr add "${ICS_PREFIX}.12/24" dev "$IF"
ip addr add "${ICS_PREFIX}.13/24" dev "$IF"
ip addr add "${ICS_PREFIX}.14/24" dev "$IF"
ip addr add "${ICS_PREFIX}.15/24" dev "$IF"

route add -net "$DMZ_SUBNET" gw "$ROUTER_ICS_IP" || true

echo "[entrypoint] Starting nginx..."
php-fpm8.2 -D
nginx

echo "[entrypoint] Starting application..."
exec "$@"
