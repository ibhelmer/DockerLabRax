#!/usr/bin/env bash
# Read-only health check from Node1; Docker routing mesh exposes all services here.
set -uo pipefail

echo "== Swarm services =="
sudo docker stack services nodered || exit 1

echo
echo "== Login + endpoint tests (HTTP, local lab only) =="
failed=0
for n in 1 2 3 4 5 6 7; do
    port=$((1900 + n))
    url="http://192.168.1.101:$port/auth/login"
    response="$(curl --connect-timeout 3 --max-time 8 -fsS "$url" 2>/dev/null)" || response=""
    if printf '%s' "$response" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"credentials"'; then
        echo "user$n (Node$n) :$port  OK (adminAuth)"
    else
        echo "user$n (Node$n) :$port  FEJL eller login-beskyttelse mangler"
        failed=1
    fi
done

echo
echo "Bemærk: Denne kontrol validerer kun HTTP-login-skemaet – ikke brugerens adgangskode, MQTT eller backup."
exit "$failed"
