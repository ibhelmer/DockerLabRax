#!/bin/sh
# Returnerer 0, hvis den lokale HAProxy accepterer TCP-forbindelser.
# Dette er et liveness-check, ikke et end-to-end MQTT-login.
exec /usr/bin/nc -z -w 2 127.0.0.1 1884
