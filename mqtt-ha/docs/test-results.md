# MQTT HA-testjournal – 15. november 2026

Disse resultater er baseret på terminaloutput fra laboratoriet. Testene viser konkret observeret adfærd; de dokumenterer ikke alle tænkelige fejlscenarier.

## Infrastruktur

| Test | Observeret resultat | Vurdering |
|---|---|---|
| HAProxy TCP/1884 på Node5 og Node6 | Begge endpoints accepterede TCP-forbindelser | Bestået |
| Keepalived valg af MASTER | Node5 priority 150 overtog VIP; Node6 priority 100 gik BACKUP | Bestået |
| MQTT via VIP 192.168.1.200:1884 | CONNACK (0), SUBACK, publiceret og modtaget testbesked | Bestået |
| VIP-failover | Efter stop af Keepalived Node5 havde Node6 192.168.1.200/24 | Bestået |
| TCP efter VIP-failover | nc til 192.168.1.200:1884 lykkedes | Bestået |
| QoS 1 publish efter VIP-failover | CONNACK (0) og PUBACK (Mid: 1, RC:0) | Bestået |

### Uddrag af Keepalived-observationer

På Node5: "received lower priority (100) advert from 192.168.1.106" og "Entering MASTER STATE".

På Node6: "Master received advert from 192.168.1.105 with higher priority 150, ours 100" og "Entering BACKUP STATE".

Disse logs dokumenterer VRRP-kommunikation med korrekt prioritet og ingen samtidig VIP på de to noder under observationen.

## Broker-failover og recovery

1. På Node1 blev mqtt_vmq2 sat til replicas 0.
2. Docker service ls viste vmq0 1/1, vmq1 1/1, vmq2 0/0.
3. En klient publicerede på ha/failover via VIP med QoS 1 og fik CONNACK (0) samt PUBACK (RC:0).
4. mqtt_vmq2 blev sat tilbage til replicas 1.
5. vmq-admin cluster show fra Node3 viste Running=true for vmq0, vmq1 og vmq2.

**Konklusion:** MQTT var fortsat tilgængelig til nye QoS 1-publiceringer ved nedlukning af én broker, og den stoppede broker genindtrådte korrekt efter restart.

## Retained messages

En besked til ha/retained-test blev publiceret med QoS 1 og retain-flag: "Temperatur 23.5 grader".

En senere subscriber modtog straks:

~~~text
Client null received PUBLISH (d0, q1, r1, ...)
ha/retained-test Temperatur 23.5 grader
~~~

**Konklusion:** Retained delivery under normal drift verificeret.

## Persistent session under normal drift

Client ID: mqtt-ha-session-test-01, MQTT 3.1.1 med clean session=false. Klienten blev afbrudt, og tre QoS 1-beskeder blev sendt til ha/offline-test.

Efter reconnect blev alle leveret og kvitteret:

~~~text
ha/offline-test Offline besked 1
ha/offline-test Offline besked 2
ha/offline-test Offline besked 3
~~~

**Konklusion:** Persistent offline-kø fungerede med den testede klient/session under normal drift.

## Lokal database efter kontrolleret broker-genstart

Testclient ID: ha-db-node4-01, broker mqtt_vmq2 på Node4.

- Persistent session og kø blev oprettet før service-stop.
- mqtt_vmq2 blev skaleret til 0 og derefter til 1.
- En ny klientforbindelse direkte til mqtt_vmq2 med samme Client ID fik alle tre tidligere køede beskeder:
  - ha/db-test/node4/offline Database besked 1
  - ha/db-test/node4/offline Database besked 2
  - ha/db-test/node4/offline Database besked 3
- En ny subscriber modtog også:
  - ha/db-test/node4/retained Database retained TEST
  - MQTT-flag r1 på den modtagne PUBLISH.

**Konklusion:** De undersøgte offline-beskeder og retained message var bevaret efter kontrolleret stop/genstart af samme broker med eksisterende lokal storage.

## Hvad er endnu ikke bevist?

- At offline-køer er tilgængelige på *andre* brokere, mens den oprindelige broker er nede.
- At beskeder overlever permanent tab af en brokers disk/SD-kort.
- At alle beskeder overlever strømtab, netværkspartitionering og samtidige fejl.
- At MQTT-klienter genopretter forbindelse automatisk i alle realtidsscenarier.
- At TLS, ACL pr. bruger og hemmelighedshåndtering er produktionsklare.
- At retain- og sessionsdata replikeres med en bestemt holdbarhedsgaranti.

## Risikoforhold

VerneMQ-stackens ALLOW_*_DURING_NETSPLIT-indstillinger er sat til on af hensyn til laboratoriets availability. Det giver risiko for inkonsistent tilstand ved netsplit. PUBACK ved QoS 1 dokumenterer ikke automatisk, at alle brokers har lagret den pågældende besked.

**Planlagt næste test:** Opret session og offline-kø på vmq2, stop vmq2, og forbind samme Client ID til vmq0/vmq1 **før** vmq2 genstartes. Dette skal udføres særskilt og må ikke forveksles med den allerede gennemførte genstarttest.
