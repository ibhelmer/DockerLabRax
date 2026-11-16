#!/usr/bin/env bash
# Opretter /srv/nodered/userN/settings.js på den tilsvarende NodeN.
# Kør lokalt på hver node: bash prepare-node.sh N
# Opretter aldrig/overskriver eksisterende konfiguration.
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[1-7]$ ]]; then
    echo "Brug: bash prepare-node.sh NUMMER (1..7)" >&2
    exit 2
fi

N="$1"
EXPECTED_HOST="Node$N"
CURRENT_HOST="$(hostname -s)"
DATA_DIR="/srv/nodered/user$N"

if [[ "$CURRENT_HOST" != "$EXPECTED_HOST" ]]; then
    echo "FEJL: Dette er $CURRENT_HOST, men user$N er planlagt til $EXPECTED_HOST." >&2
    exit 1
fi

if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "FEJL: Node-RED 5.0.9-24 kræver 64-bit arm64 (aarch64)." >&2
    echo "Den aktuelle arkitektur er: $(uname -m)" >&2
    exit 1
fi

if sudo test -e "$DATA_DIR/settings.js"; then
    echo "FEJL: $DATA_DIR/settings.js findes allerede; intet bliver overskrevet." >&2
    exit 1
fi

if ! python3 -c 'import bcrypt' >/dev/null 2>&1; then
    echo "Installerer python3-bcrypt til sikker hashing af editoradgangskoden ..."
    sudo apt-get update
    sudo apt-get install -y python3-bcrypt
fi

HASH="$(python3 - <<'PY'
import bcrypt
import getpass
import sys

p1 = getpass.getpass("Vaelg adgangskode til Node-RED editor (min. 12 tegn): ")
p2 = getpass.getpass("Gentag adgangskoden: ")
if p1 != p2:
    sys.exit("FEJL: Adgangskoderne er ikke ens")
if len(p1) < 12:
    sys.exit("FEJL: Adgangskoden skal vaere mindst 12 tegn")
print(bcrypt.hashpw(p1.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii"))
PY
)"

# Credential secret krypterer credentials i flows_cred.json; maa ikke skiftes
# efter det er sat, medmindre credentials er eksporteret og skal gendannes.
CREDENTIAL_SECRET="$(openssl rand -hex 32)"

umask 077
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/settings.js" <<EOF
// Lokalt genereret og privat Node-RED-konfiguration for user$N.
// Commit IKKE denne fil til GitHub (unik credentialSecret og bcrypt-hash).
module.exports = {
    uiPort: process.env.PORT || 1880,
    credentialSecret: "$CREDENTIAL_SECRET",
    adminAuth: {
        type: "credentials",
        users: [{
            username: "user$N",
            password: "$HASH",
            permissions: "*"
        }]
    },
    // Beskyt ogsaa HTTP In-endpoints med Basic Auth.
    // Hvis undervisningsopgaver kraever offentlige webhooks, kraever de
    // saerskilt sikkerhedsdesign, før dette aendres.
    httpNodeAuth: {
        user: "user$N",
        pass: "$HASH"
    }
};
EOF

sudo install -d -m 0700 -o 1000 -g 1000 "$DATA_DIR"
sudo install -m 0600 -o 1000 -g 1000 "$TMP_DIR/settings.js" "$DATA_DIR/settings.js"

echo "KLAR: $EXPECTED_HOST / user$N"
echo "Data: $DATA_DIR (ejer 1000:1000)"
echo "Planlagt URL: http://192.168.1.$((100 + N)):1880"
echo "Din editoradgangskode er ikke gemt i klartekst."
echo "Husk backup af settings.js, flows.json og credentials i /data."
