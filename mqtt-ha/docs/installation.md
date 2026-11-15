# Installation og genopbygning

Denne guide dokumenterer den fungerende topologi; den udfører **ikke** en automatisk migration. Brug eksisterende Portainer-stacks som sandhedskilde, når de afviger fra eksemplerne.

## 1. Forudsætninger

- Raspberry Pi OS Lite, Docker Engine/Swarm og administratoradgang på syv noder med hostname Node1–Node7.
- Statiske adresser Node1 = 192.168.1.101 ... Node7 = 192.168.1.107.
- Node1, Node2 og Node3 er Swarm-managers. Node4–Node7 er workers.
- VerneMQ-brokerne kører på Node3 (vmq0), Node2 (vmq1), Node4 (vmq2).
- HAProxy og Keepalived kører på Node5 og Node6.
- Sørg for, at 192.168.1.200 er ledig og ikke kan udleveres via DHCP.

Fra en manager kan du se status:

~~~bash
sudo docker node ls
sudo docker service ls
sudo docker network inspect mqtt-core
~~~

## 2. Swarm labels og overlay-netværk

Kør disse kommandoer på Node1, hvis du opbygger miljøet fra bunden. Kontroller labels og netværk, før du forsøger at oprette dem igen.

~~~bash
sudo docker node update --label-add mqtt.broker=vmq0 Node3
sudo docker node update --label-add mqtt.broker=vmq1 Node2
sudo docker node update --label-add mqtt.broker=vmq2 Node4
sudo docker node update --label-add mqtt.proxy=true Node5
sudo docker node update --label-add mqtt.proxy=true Node6
sudo docker network create --driver overlay --attachable \
  --subnet 10.77.20.0/24 mqtt-core
~~~

Swarm initialiseres på Node1 med annonceringsadressen 192.168.1.101. Tilslut Node2/Node3 som managers og de øvrige som workers med join-tokens fra Swarm. Brug ikke gamle join-tokens fra før geninstallationen.

## 3. Persistente mapper på Node2, Node3 og Node4

~~~bash
sudo mkdir -p /srv/vernemq/{data,etc,log}
~~~

Kontroller ejerskab/rettigheder i forhold til det VerneMQ-image, der reelt kører. Genbrug ikke en LevelDB-mappe fra en broker med en anden Erlang-identitet.

**Slet aldrig /srv/vernemq/data som led i normal fejlfinding.** Den rummer lokale persistente MQTT-data.

## 4. VerneMQ gennem Portainer

Brug [stacks/vernemq.yml](../stacks/vernemq.yml) som reference for stacken med navnet **mqtt**.

- Docker-image: vernemq/vernemq:2.2.1.
- Hostname/Erlang-identitet: vmq0.mqtt.internal, vmq1.mqtt.internal, vmq2.mqtt.internal.
- Bind mounts: /srv/vernemq/{data,etc,log} til /vernemq/{data,etc,log}.
- Placement: mqtt.broker=vmq0/vmq1/vmq2 på de korrekte noder.
- Endpoint mode: dnsrr; tilslut mqtt-core.
- Password: sæt Portainer stack-variable MQTT_PASSWORD lokalt; commit aldrig værdien.
- Ønsket steady state: **replicas: 1** for alle tre services.

Kontroller altid de aktuelt kørende service-specifikationer, før du opdaterer stacken:

~~~bash
sudo docker service inspect mqtt_vmq0 --pretty
sudo docker service inspect mqtt_vmq1 --pretty
sudo docker service inspect mqtt_vmq2 --pretty
~~~

Ved en **helt ny/tom** installation startes seed-broker vmq0 først; vmq1 og vmq2 kan derefter sluttes til clusteret med:

~~~bash
# Fra den relevante broker-container, kun ved førstegangs cluster-opbygning:
vmq-admin cluster join discovery-node=VerneMQ@vmq0.mqtt.internal
vmq-admin cluster show
~~~

Udfør ikke join på et allerede sundt cluster. Uoverensstemmelse mellem lokal LevelDB og nodens identitet kan give fejlen non_empty_node.

## 5. HAProxy med ekstern Docker config

[config/haproxy.cfg](../config/haproxy.cfg) indeholder TCP-balancering med backend-serverne mqtt_vmq0, mqtt_vmq1 og mqtt_vmq2.

Docker config skal være oprettet med navnet **mqtt-haproxy-v3**, før [stacks/mqtt-lb.yml](../stacks/mqtt-lb.yml) deployes som stack **mqtt-lb**. Fra mappen mqtt-ha på Node1:

~~~bash
sudo docker config create mqtt-haproxy-v3 config/haproxy.cfg
~~~

Hvis Docker config allerede findes, skal du **ikke** oprette den igen. Docker configs er immutable; ved ændringer bruges fx nyt navn mqtt-haproxy-v4 samt opdateret stackreference.

HAProxy kører i host publishing-mode på TCP/1884 på Node5 og Node6.

~~~bash
nc -vz -w 3 192.168.1.105 1884
nc -vz -w 3 192.168.1.106 1884
~~~

## 6. Keepalived på Node5 og Node6

Installér på **begge**:

~~~bash
sudo apt update
sudo apt install -y keepalived netcat-openbsd tcpdump
ip -br -4 addr show
~~~

Der forventes eth0 som LAN-interface. Kopiér den relevante konfiguration **til den tilsvarende node**:

- Node5: [keepalived-node5.conf](../config/keepalived-node5.conf), unicast source .105, peer .106, priority 150.
- Node6: [keepalived-node6.conf](../config/keepalived-node6.conf), unicast source .106, peer .105, priority 100.
- Begge: [check-mqtt-haproxy.sh](../scripts/check-mqtt-haproxy.sh) til /usr/local/sbin/check-mqtt-haproxy.sh.

Installér health-scriptet og config på hver node:

~~~bash
sudo install -m 755 check-mqtt-haproxy.sh /usr/local/sbin/check-mqtt-haproxy.sh
sudo install -m 644 keepalived-nodeX.conf /etc/keepalived/keepalived.conf
sudo keepalived -t
sudo systemctl enable --now keepalived
~~~

Tilpas filstierne til den lokale checkout og erstat nodeX med 5 eller 6. Start gerne Node6 først og derefter Node5. Tillad **VRRP/IP-protokol 112** mellem Node5 og Node6 i eventuelle firewalls.

Kun én node må eje VIP'en 192.168.1.200 ad gangen.

~~~bash
ip -br -4 addr show dev eth0
sudo journalctl -u keepalived -n 35 --no-pager
~~~

## 7. Slutkontrol

~~~bash
sudo docker service ls
nc -vz -w 3 192.168.1.200 1884
~~~

MQTT på VIP skal testes med et faktisk MQTT CONNECT og QoS 1 PUBLISH/SUBSCRIBE; en åben TCP-port alene beviser ikke applikationsfunktion.

Fortsæt med [drift og tests](operations.md).
