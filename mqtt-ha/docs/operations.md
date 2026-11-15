# Daglig drift, status og fejlfinding

Alle Docker Swarm-kommandoer køres på Node1, medmindre andet er angivet.

## Status

~~~bash
sudo docker node ls
sudo docker service ls
sudo docker service ps mqtt_vmq0
sudo docker service ps mqtt_vmq1
sudo docker service ps mqtt_vmq2
sudo docker service ps mqtt-lb_haproxy
~~~

Forventet: VerneMQ 1/1 på hver af de tre brokere, HAProxy 2/2, Portainer agent 7/7.

Clusterstatus på Node3:

~~~bash
CID=$(sudo docker ps -q -f label=com.docker.swarm.service.name=mqtt_vmq0)
sudo docker exec "$CID" vmq-admin cluster show
~~~

Forventet Running = true for VerneMQ@vmq0.mqtt.internal, VerneMQ@vmq1.mqtt.internal og VerneMQ@vmq2.mqtt.internal.

Logs:

~~~bash
sudo docker service logs --tail 100 mqtt_vmq2
sudo docker service logs --tail 100 mqtt-lb_haproxy
~~~

## MQTT-adgang

- Fast adresse: **192.168.1.200:1884** (VIP).
- Node5 direkte: 192.168.1.105:1884.
- Node6 direkte: 192.168.1.106:1884.
- Intern VerneMQ: TCP/1883 via mqtt-core.
- Login: iotuser og lokalt lagret adgangskode.

~~~bash
nc -vz -w 3 192.168.1.200 1884
~~~

Test med Mosquitto-klienter. Brug interaktiv indtastning af adgangskoder, ikke hardkodede secrets i scripts eller shellhistorik.

## Kontrolleret broker-failover (Node4/vmq2)

**Kun i et vedligeholdelsesvindue med testklienter.** Bekræft først, at vmq0 og vmq1 er sunde:

~~~bash
sudo docker service scale mqtt_vmq2=0
sudo docker service ls
# Gentag MQTT PUBLISH/SUBSCRIBE via 192.168.1.200:1884
sudo docker service scale mqtt_vmq2=1
sudo docker service ps mqtt_vmq2
~~~

Kontroller derefter clusterstatus fra Node3. Bevar /srv/vernemq/data – ingen rydning, join eller geninitialisering under testen. Skalering til 0 er et kontrolleret service-stop, **ikke** simulering af strøm-/diskhavari.

## Keepalived-failover

Kontrollér først at VIP kun findes på én node.

Node5:

~~~bash
sudo systemctl stop keepalived
~~~

Node6:

~~~bash
ip -br -4 addr show dev eth0
# Skal indeholde 192.168.1.200/24
~~~

Node1: Test TCP og MQTT PUBLISH via VIP. Gendan Node5:

~~~bash
sudo systemctl start keepalived
~~~

Node5 bør igen få VIP med prioritet 150. **Eksisterende MQTT/TCP-sessioner kan blive afbrudt** og klienter skal have reconnect. Hvis begge noder ejer VIP, stop Keepalived på Node6 og undersøg VRRP-pakker/IP-protokol 112 og src/peer-adresser.

## Databevaring og gendannelse

- Retained message: publicér med QoS 1 og retain-flag, forbind en ny subscriber.
- Persistent session: MQTT 3.1.1 med fast Client ID, clean session=false, QoS 1; afbryd subscriber, publicér offline, forbind igen.
- Genstart af samme broker med samme lokale bind mount: observer om køede beskeder og retained messages gendannes.
- **Ikke verificeret:** fuld datatilgængelighed under permanent tab af lokal storage, pludseligt strømsvigt og gensidig replikering af offline-køer.

Se [testresultater](test-results.md). MQTT QoS 1 og PUBACK betyder ikke automatisk replikeret eller fuldt crash-sikkert lagring på alle brokere.

## Vigtig recovery-regel

Kør **ikke** disse kommandoer rutinemæssigt:

- Sletning af /srv/vernemq/data.
- vmq-admin cluster leave / gentagne cluster join på eksisterende medlemmer.
- Udskiftning af DOCKER_VERNEMQ_NODENAME eller hostname for en eksisterende datamappe.

Ved en fejl: gem docker service ps/logs og vmq-admin cluster show, før du foretager ændringer.
