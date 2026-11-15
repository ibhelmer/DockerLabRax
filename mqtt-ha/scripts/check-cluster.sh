#!/usr/bin/env bash
# Read-only statuskontrol for MQTT HA-laboratoriet.
# Kør på Node1: bash mqtt-ha/scripts/check-cluster.sh
set -uo pipefail

echo "== Docker Swarm services =="
sudo docker service ls || exit 1

echo
echo "== Broker placement / tasks =="
for service in mqtt_vmq0 mqtt_vmq1 mqtt_vmq2 mqtt-lb_haproxy; do
  echo "--- $service ---"
  sudo docker service ps "$service" --no-trunc || true
done

echo
echo "== TCP-test af HAProxy / VIP =="
for host in 192.168.1.105 192.168.1.106 192.168.1.200; do
  printf '%s:1884: ' "$host"
  if nc -z -w 3 "$host" 1884 >/dev/null 2>&1; then
    echo "TCP OK"
  else
    echo "TCP FEJL"
  fi
done

echo
echo "== VerneMQ clusterstatus på Node3 =="
SSH_USER="$USER"
ssh -t "$SSH_USER@192.168.1.103" \
  'CID=$(sudo docker ps -q -f label=com.docker.swarm.service.name=mqtt_vmq0); test -n "$CID" && sudo docker exec "$CID" vmq-admin cluster show' \
  || echo "Kunne ikke hente clusterstatus via SSH; kontrollér SSH/sudo."

echo
echo "== Bemærk =="
echo "TCP OK er ikke en MQTT-login- eller ACL-test."
echo "Scriptet ændrer ingen services, passwords eller konfigurationer."
