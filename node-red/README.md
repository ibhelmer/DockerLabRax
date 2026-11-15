# Syv Node-RED-instanser til syv brugere

Separat Node-RED pr. bruger i Docker Swarm på DockerLabRax, Raspberry Pi Node1–Node7. Image: **nodered/node-red:5.0.9-24**. En bruger = en selvstændig container, login, flowmappe og krypteringsnøgle. Dette er til et internt undervisningslaboratorium.

## Fordeling

| Bruger | Placering | Port | URL via Node1 | Persistens |
|---|---|---:|---|---|
| user1 | Node1 | 1901 | http://192.168.1.101:1901 | /srv/nodered/user1 på Node1 |
| user2 | Node2 | 1902 | http://192.168.1.101:1902 | /srv/nodered/user2 på Node2 |
| user3 | Node3 | 1903 | http://192.168.1.101:1903 | /srv/nodered/user3 på Node3 |
| user4 | Node4 | 1904 | http://192.168.1.101:1904 | /srv/nodered/user4 på Node4 |
| user5 | Node5 | 1905 | http://192.168.1.101:1905 | /srv/nodered/user5 på Node5 |
| user6 | Node6 | 1906 | http://192.168.1.101:1906 | /srv/nodered/user6 på Node6 |
| user7 | Node7 | 1907 | http://192.168.1.101:1907 | /srv/nodered/user7 på Node7 |

Alle containere bruger internt TCP/1880. Swarm routing mesh publicerer portene 1901–1907 på ALLE Swarm-noder, ikke kun Node1. MQTT VIP 192.168.1.200:1884 berøres ikke.

**Vigtigt:** Bind mounts + faste placement constraints betyder, at hver brugers data opbevares på én bestemt node. Der er IKKE Node-RED-HA. Hvis Node4 er nede, er user4 offline, indtil Node4 eller data gendannes.

## 1. Kontrol før installation

Kontroller på alle syv noder:

~~~bash
hostname -s
uname -m
free -h
~~~

Hostnames skal hedde Node1 til Node7. Image version 5 kræver 64-bit arm64/aarch64; 32-bit Raspberry Pi OS kan ikke anvende dette image. Vurder ledig RAM, CPU og disk, især på MQTT-brokerne og HAProxy-noderne. Stacken har 512 MB RAM-grænse pr. bruger og én replica pr. service.

## 2. Opret login og persistente filer

Kør på hver node med din normale sudo-bruger:

~~~bash
curl -fsSLo /tmp/prepare-node.sh \
  https://raw.githubusercontent.com/ibhelmer/DockerLabRax/main/node-red/scripts/prepare-node.sh
bash /tmp/prepare-node.sh N
~~~

Erstat N med nodens nummer. På Node3:

~~~bash
bash /tmp/prepare-node.sh 3
~~~

Scriptet kontrollerer hostname og aarch64, beder om en unik adgangskode to gange (mindst 12 tegn), gemmer bcrypt-hash og genererer et unikt credentialSecret. Output er /srv/nodered/userN/settings.js med ejerskab 1000:1000 og rettigheder 0600.

Scriptet overskriver IKKE eksisterende settings.js. Filen indeholder passwordhash og krypteringsnøgle og skal holdes uden for GitHub. Beskyt en backup af hele /data-mappen.

Alternativt kan du starte scriptet på en fjernnode fra Node1 med SSH (kræver SSH/sudo-adgang):

~~~bash
ssh -tt ihn@192.168.1.103 \
  'curl -fsSLo /tmp/prepare-node.sh https://raw.githubusercontent.com/ibhelmer/DockerLabRax/main/node-red/scripts/prepare-node.sh && bash /tmp/prepare-node.sh 3'
~~~

## 3. Deploy i Docker Swarm fra Node1

~~~bash
git clone https://github.com/ibhelmer/DockerLabRax.git
cd DockerLabRax
sudo docker stack deploy -c node-red/stack.yml nodered
sudo docker stack services nodered
~~~

Alternativt indsættes node-red/stack.yml i Portainer → Stacks → Add stack med navnet nodered.

De syv service-navne er nodered_user1 til nodered_user7. Hver skal være 1/1. Fejl findes med:

~~~bash
sudo docker service ps nodered_user3
sudo docker service logs --tail 60 nodered_user3
~~~

Hvis en service er Pending: kontroller NodeN hostname, arkitektur og placering. Hvis Permission denied: kontroller ejerskab 1000:1000 på /srv/nodered/userN.

## 4. Test login

~~~bash
curl -fsS http://192.168.1.101:1901/auth/login
curl -fsS http://192.168.1.101:1907/auth/login
bash node-red/scripts/check-instances.sh
~~~

Svaret fra /auth/login skal indeholde type: credentials, ellers er editor-login ikke aktiveret som forventet. Besøg adressen til den enkelte bruger og log ind med userN og den adgangskode, du selv valgte.

adminAuth beskytter editor og Admin API. httpNodeAuth er også aktiveret, så HTTP In-endpoints kræver HTTP Basic Auth. Dette kan kræve tilpasning, hvis brugerne bygger åbne REST-API'er.

## 5. MQTT-forbindelse

Hver bruger kan konfigurere MQTT-broker-noden i Node-RED til:

- Server: 192.168.1.200
- Port: 1884
- Client ID: eksempelvis nodered-user3 (unikt)
- MQTT-login: separat MQTT-brugernavn/adgangskode, IKKE Node-RED-editorlogin.

Opret egne MQTT-brugere og topic-ACL pr. bruger i VerneMQ, eksempelvis:

~~~text
user nodered03
topic read students/user3/#
topic write students/user3/#
~~~

Se ../mqtt-ha/docs/user-management.md. Den tidligere Python-brugermanager er endnu ikke verificeret end-to-end i levende cluster. Test ACL direkte mod alle tre brokere.

## 6. Backup og begrænsninger

- /srv/nodered/userN indeholder flows, credentials, settings.js og installerede nodes; tag backup af hele mappen.
- Skift ikke credentialSecret ved genstart eller opgradering: det kan gøre eksisterende credentials ulæselige.
- De syv Node-RED-instanser er isoleret på containerniveau, men er ikke en stærk sikkerhedsgrænse som syv separate VM'er.
- Udsæt ikke denne HTTP-installation på internettet; anvend HTTPS/reverse proxy og adgangsbegrænsning før eksterne klienter. Passwords til både editor og Basic Auth sendes ellers uden TLS.
- Docker Swarm routing mesh kan acceptere 1901–1907 på alle noder; begræns firewall til undervisningsnettet.
- Del ikke Docker socket eller vilkårlige host-mapper med studentercontainere. Node-RED-flows kan anvende noder med betydelige runtime-rettigheder.
- Placeringsreglerne er faste for at beskytte lokal persistens. Skal en instans flyttes til en anden Pi, kræver det kontrolleret datamigrering eller shared storage.

## Referencer

- https://nodered.org/docs/getting-started/docker
- https://nodered.org/docs/user-guide/runtime/securing-node-red
- https://docs.docker.com/engine/swarm/ingress/
