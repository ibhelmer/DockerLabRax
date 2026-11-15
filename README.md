# DockerLabRax
Docker swarm rack med 7 noder, med Raspberry pi 4b

## MQTT High Availability-laboratorium

Denne del af Docker Swarm-laboratoriet dokumenterer MQTT HA på syv Raspberry Pi 4 med VerneMQ, HAProxy, Keepalived og Portainer.

- [MQTT HA – arkitektur, konfiguration og vejledninger](mqtt-ha/README.md)
- [Installationsvejledning](mqtt-ha/docs/installation.md)
- [Drift og fejlfinding](mqtt-ha/docs/operations.md)
- [HA-testjournal](mqtt-ha/docs/test-results.md)
- [Brugeradministration og ACL](mqtt-ha/docs/user-management.md)
- [Sikkerhed, begrænsninger og backup](mqtt-ha/docs/security.md)

**Bemærk:** Det tilhørende MQTT-endpoint er dokumenteret for et internt test-/undervisningsnet. De uploadede konfigurationsfiler er referencefiler og skal sammenlignes med det faktiske Portainer-/Docker-setup før genudrulning. Ingen adgangskoder gemmes her.

## Node-RED til syv brugere

Projektet indeholder nu syv selvstændige Node-RED-services, én på hver Raspberry Pi, med portene 1901–1907, individuelle bcrypt-login og hver sin persistente /data-mappe.

- [Node-RED installationsvejledning og brugerfordeling](node-red/README.md)
- [Docker Swarm stack til alle syv instanser](node-red/stack.yml)
- [Script til oprettelse af lokale brugerindstillinger](node-red/scripts/prepare-node.sh)
- [Statuskontrol af syv Node-RED-instanser](node-red/scripts/check-instances.sh)

**Sikkerhed:** Node-RED eksempelstacken bruger HTTP til internt lab. Den er ikke beregnet til direkte eksponering på internettet. Den faktiske adgangskode og settings.js må ikke tilføjes til GitHub.
