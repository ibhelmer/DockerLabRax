# MQTT High Availability Lab (Raspberry Pi 4 / Docker Swarm)

Dokumentation og konfigurationsskabeloner til det afprøvede MQTT-laboratorium på syv Raspberry Pi 4. Miljøet benytter Docker Swarm, VerneMQ 2.2.1, HAProxy 3.2 og Keepalived med én virtuel IPv4-adresse.

**Status:** MQTT, broker-genindtræden, VIP-failover, QoS 1, retained messages og lokal genopretning af offline-kø er testet den 15. november 2026. Dette er et undervisnings-/testlab, ikke en certificeret produktionsinstallation.

## Arkitektur

| Node | LAN-IP | Funktion |
|---|---|---|
| Node1 | 192.168.1.101 | Swarm manager, Portainer, administration |
| Node2 | 192.168.1.102 | Swarm manager, VerneMQ vmq1 |
| Node3 | 192.168.1.103 | Swarm manager, VerneMQ vmq0 |
| Node4 | 192.168.1.104 | Swarm worker, VerneMQ vmq2 |
| Node5 | 192.168.1.105 | Swarm worker, HAProxy + Keepalived (prioritet 150) |
| Node6 | 192.168.1.106 | Swarm worker, HAProxy + Keepalived (prioritet 100) |
| Node7 | 192.168.1.107 | Swarm worker / ledig labkapacitet |

- **MQTT-endpoint:** 192.168.1.200:1884 (VIP på Node5 eller Node6).
- **MQTT internt:** TCP/1883 på VerneMQ-brokerne.
- **Overlay-netværk:** mqtt-core (attachable), 10.77.20.0/24.
- **VerneMQ servicenames:** mqtt_vmq0, mqtt_vmq1, mqtt_vmq2.
- **HAProxy-service:** mqtt-lb_haproxy, én instans på Node5 og Node6.
- **Data pr. broker:** /srv/vernemq/data, /srv/vernemq/etc og /srv/vernemq/log.
- **MQTT-bruger:** iotuser via variablen MQTT_PASSWORD; anonym adgang slået fra.

~~~
MQTT-clients --> 192.168.1.200:1884 (VIP, Keepalived)
                                  |
                       +----------+----------+
                       |                     |
                   Node5 HAProxy         Node6 HAProxy
                   MASTER normalt        BACKUP normalt
                       +----------+----------+
                                  |
                            mqtt-core overlay
                                  |
                   +--------------+--------------+
                   |              |              |
               Node3/vmq0     Node2/vmq1      Node4/vmq2
~~~

## Filer

- [Installation og genopbygning](docs/installation.md)
- [Drift, kontrol og fejlfinding](docs/operations.md)
- [Testresultater og begrænsninger](docs/test-results.md)
- [MQTT-brugere og ACL](docs/user-management.md)
- [Sikkerhed og backup](docs/security.md)
- [VerneMQ stack](stacks/vernemq.yml) – rettet til tre ønskede replicas (1/1/1).
- [HAProxy stack](stacks/mqtt-lb.yml)
- [HAProxy TCP-konfiguration](config/haproxy.cfg)
- [Keepalived Node5](config/keepalived-node5.conf) og [Node6](config/keepalived-node6.conf)
- [Keepalived health check](scripts/check-mqtt-haproxy.sh)
- [Statuskontrol (read-only)](scripts/check-cluster.sh)
- [Python MQTT User Manager](scripts/mqtt_user_manager.py) – kræver preflight og lokal validering.

## Vigtigt inden anvendelse

Filerne er baseret på de senest delte konfigurationer og testlogs. Der er **ikke** foretaget et live-eksport af Docker-/Portainer- eller Keepalived-konfigurationerne, så sammenlign altid med driftssystemet **før** en redeploy. Alle hemmeligheder skal forblive uden for GitHub. Repoet er offentligt.

MQTT på port 1884 er ukrypteret i denne installation. Til produktion skal TLS, adgangsbegrænsning, backup/restore og egentlige fejlsimuleringer gennemføres. Netsplit-indstillingerne i labbet prioriterer availability frem for konsistens.
