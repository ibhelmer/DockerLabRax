# MQTT-brugere og topic-ACL

Den nuværende installation benytter VerneMQ med anonym adgang slået fra. Den eksisterende iotuser er defineret som DOCKER_VERNEMQ_USER_IOTUSER i Portainer-stacken; adgangskoden ligger i den lokale stackvariabel MQTT_PASSWORD og må **aldrig** committes til GitHub.

## Central administration

[Python-scriptet mqtt_user_manager.py](../scripts/mqtt_user_manager.py) er et administrationsværktøj, som blev udarbejdet til dette lab. Scriptet arbejder over SSH fra Node1 til:

| Broker | Node | SSH-IP |
|---|---|---|
| mqtt_vmq0 | Node3 | 192.168.1.103 |
| mqtt_vmq1 | Node2 | 192.168.1.102 |
| mqtt_vmq2 | Node4 | 192.168.1.104 |

Det opretter en passwordhash med vmq-passwd på Node3, synkroniserer hash-entry og administrerede ACL-blokke til alle tre brokere, og tager backups af filer inden ændringer.

**Vigtig status:** Python-syntaksen er kontrolleret, men scriptets end-to-end-funktion er **ikke** verificeret i dit levende cluster. Brug derfor først check, inspicér de aktuelle password-/ACL-filer og tag en ekstra sikkerhedskopi. Det er ikke et generelt produktionsklart identity management-system.

## Forudsætninger

- Python 3 på Node1 og SSH fra Node1 til Node2/3/4.
- Kontonavn: Scriptet bruger SSH_USER = "ihn" som default. Redigér variablen, hvis dit miljø ændres.
- sudo-rettigheder på brokernoderne.
- Korrekt persistente filer /srv/vernemq/etc/vmq.passwd og /srv/vernemq/etc/vmq.acl på de tre noder.
- VerneMQs filbaserede auth/ACL-plugins skal være aktive.
- Ingen globale pattern-regler, der utilsigtet giver bredere adgang.
- Kontoen skal endnu ikke findes i nogen af passwordfilerne/ACL-filerne.

## Kontrol

På Node1 fra repoets rodmappe:

~~~bash
python3 mqtt-ha/scripts/mqtt_user_manager.py check
~~~

Hvis kontrollen stopper, fordi vmq.acl mangler, skal ACL-plugin og den aktive config inspiceres **før** du opretter filen eller aktiverer scriptet.

## Opret bruger og regler

Eksempel med en sensor, der må publicere målinger og abonnere på kommandoer:

~~~bash
python3 mqtt-ha/scripts/mqtt_user_manager.py add sensor01 \
  --pub 'sensors/sensor01/#' \
  --sub 'commands/sensor01/#'
~~~

Genereret ACL-indhold i det administrerede afsnit:

~~~text
user sensor01
topic write sensors/sensor01/#
topic read commands/sensor01/#
~~~

Andre eksempler:

~~~bash
python3 mqtt-ha/scripts/mqtt_user_manager.py add nodered \
  --pub 'commands/#' \
  --sub 'sensors/#' \
  --sub 'status/#'
~~~

## ACL-fortolkning

- topic write = tillad PUBLISH til matchende topic-filter.
- topic read = tillad SUBSCRIBE/læsning fra matchende filter.
- # matcher flere topicniveauer; + ét niveau.
- Rettigheder skal være konsistente på alle tre brokere.
- VerneMQs faktiske autorisation afhænger af aktive plugins og øvrige ACL-regler. **Test både tilladt og afvist adgang** med en testkonto.

## Begrænsninger og advarsler

- Scriptet implementerer oprettelse og check, **ikke** sletning, adgangskodeskift eller revision af eksisterende bruger.
- En ændring kan kun delvist lykkes, hvis en broker mister SSH-forbindelsen midt i processen. Gennemgå alle tre filer efter eventuelle fejl.
- Scriptet må ikke køres parallelt af flere administratorer.
- Passwordhash og ACL er *ikke* en central database. Hver broker har egne filer.
- Kombinationen af Docker-miljøvariabler for eksisterende brugere og filbaseret administration af nye brugere skal valideres ved broker-genstart.
- Fil-ACL'er og ACL-regler skal kontrolleres for uventede generelle tilladelser, før mindst-privilegieprincippet kan garanteres.

## Verificér en ny bruger

Brug MQTT-klienter mod 192.168.1.200:1884. Kontrollér CONNACK 0 og PUBACK for lovligt publish, men også at et ulovligt topic ikke kan læses/publiceres. Test derefter direkte mod alle tre brokere fra en container på mqtt-core-netværket for at udelukke uens password-/ACL-filer.

**Gem ikke passwords, vmq.passwd, private nøgler eller fulde runtime-konfigurationer med secrets i repoet.**
