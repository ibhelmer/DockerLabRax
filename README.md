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
