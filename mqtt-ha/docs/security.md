# Sikkerhed, begrænsninger og backup

## GitHub-repoet er offentligt

Derfor indeholder filerne alene eksempler, topology og konfigurationsskabeloner. Læg **aldrig** følgende i git:

- MQTT_PASSWORD, brugernavne med adgangskoder, Portainer API tokens eller Docker Swarm join-tokens.
- /srv/vernemq/etc/vmq.passwd (hashes), private SSH- eller TLS-nøgler.
- Runtime dumps fra docker inspect, hvis de indeholder miljøvariabler med hemmeligheder.
- Komplette backups eller LevelDB-data med MQTT-payloads.

.gitignore beskytter kun mod utilsigtede git add og kan omgås med force; kontrollér altid git diff --cached før commit.

## MQTT og kryptering

Det dokumenterede endpoint **192.168.1.200:1884 er almindelig TCP/MQTT uden TLS**. Anvend kun på betroede net indtil TLS med certifikater og klientvalidering er konfigureret. Eksponér ikke porten direkte mod internettet. TLS på eksempelvis TCP/8883 er en separat opgave og er ikke testet.

## Adgangskontrol

- Anonym adgang er slået fra.
- Brug individuelle MQTT-brugere og mindst mulige topic-ACL'er.
- Den initiale iotuser oprettes via Docker/Portainer-miljøvariabel; pas på, at den ikke lækkes via docker service inspect, support-logs eller screenshots.
- Password- og ACL-filer på de tre brokere skal være konsistente.
- Brugeradministrationsscriptet er endnu ikke end-to-end-testet; se [user-management.md](user-management.md).

## HA og datakonsistens

Docker Swarm, HAProxy og Keepalived leverer ikke en automatisk garanti for replikerede offline-køer. Brokerens lokale /srv/vernemq/data skal bevares, hvis dens data skal kunne gendannes.

Lab-konfigurationen anvender:

~~~text
DOCKER_VERNEMQ_ALLOW_REGISTER_DURING_NETSPLIT=on
DOCKER_VERNEMQ_ALLOW_PUBLISH_DURING_NETSPLIT=on
DOCKER_VERNEMQ_ALLOW_SUBSCRIBE_DURING_NETSPLIT=on
DOCKER_VERNEMQ_ALLOW_UNSUBSCRIBE_DURING_NETSPLIT=on
~~~

Disse indstillinger prioriterer servicekontinuitet under partitionering men kan indebære inkonsistens. Anvend ikke uændret i produktion uden designgennemgang af fejltolerance og datakonsistens.

Keepalived kører i unicast VRRP mellem 192.168.1.105 og .106. Firewalls må ikke blokere IP-protokol 112 mellem de to noder; tillad den kun mellem autoriserede peers.

## Backup/restore

For et lab anbefales dokumenteret periodisk backup af de tre brokers lokale mapper: /srv/vernemq/data, /srv/vernemq/etc og evt. logs. Backup af en aktiv LevelDB-database ved blot at kopiere filer kan være inkonsistent. Planlæg en konsistent snapshot-/stopprocedure **broker for broker**, verificér backupfiler og gennemfør restore-test i et *isoleret* testmiljø.

Bevar samme nodeidentitet (hostname/Erlang nodename) ved restore, medmindre der udføres en planlagt fuld cluster-migration. Udskift ikke en brokers database med en andens database.

## Før produktionsbrug

1. Implementér TLS/mTLS efter behov og verificér certifikatkæden.
2. Indfør og test individuelle ACL'er, adgangskoderotation og logning.
3. Etablér backup og dokumenteret restore-test.
4. Test pludseligt strømudfald, netværkspartitionering og klient-reconnect.
5. Overvåg VRRP, backend-health, disk/SD-kort, memory og offline-køer.
6. Overvej UPS og mere robust storage end almindelige SD-kort.
