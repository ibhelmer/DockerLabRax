#!/usr/bin/env python3
"""Administrer VerneMQ filbaserede MQTT-brugere + ACL på Node2/3/4.
Køres på Node1. Password indtastes via den officielle vmq-passwd på Node3.
Kræver SSH (bruger ihn) og sudo på brokernoderne.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SSH_USER = "ihn"
BROKERS = {
    "Node3": ("192.168.1.103", "mqtt_vmq0"),
    "Node2": ("192.168.1.102", "mqtt_vmq1"),
    "Node4": ("192.168.1.104", "mqtt_vmq2"),
}
MASTER = "Node3"
ETC = Path("/srv/vernemq/etc")
REMOTE_DIR = f"/home/{SSH_USER}/.mqtt-admin"
REMOTE_SCRIPT = REMOTE_DIR + "/mqtt_user_manager.py"
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
START_MARKER = "# BEGIN MQTT-USER-MANAGER:"
END_MARKER = "# END MQTT-USER-MANAGER:"


def error(msg):
    raise RuntimeError(msg)


def validate_topic(t):
    if not t or t.strip() != t or any(x in t for x in ("\n", "\r", "\0", " ")):
        error(f"Ugyldigt topic: {t!r}")
    if len(t) > 256:
        error("Topic må højst være 256 tegn i dette værktøj")
    for p in t.split("/"):
        if ("#" in p and p != "#") or ("+" in p and p != "+"):
            error("MQTT-wildcards skal udgøre et helt topicniveau")
    if "#" in t.split("/")[:-1]:
        error("# må kun stå på sidste topicniveau")
    # Undgå kontrollinjer, selv om MQTT ellers tillader mange UTF-8 tegn
    if not re.fullmatch(r"[A-Za-z0-9_./+#%-]+", t):
        error(f"Uventet tegn i topic: {t!r}")
    if t.startswith("$"):
        error("Systemtopics ($...) understøttes ikke af dette automatiseringsscript")


def run(cmd, capture=False, tty=False):
    if not capture:
        subprocess.run(cmd, check=True)
        return ""
    # Vis sudo-/SSH-prompts direkte, men undlad at vise resultater,
    # der kan indeholde en adgangskodehash.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    collected = []
    pending = ""
    marker = "MQTT_RESULT:"
    while True:
        raw = proc.stdout.read(1)
        if not raw:
            break
        ch = raw.decode("utf-8", errors="replace")
        collected.append(ch)
        pending += ch
        if pending.startswith(marker):
            if ch in ("\r", "\n"):
                pending = ""
            continue
        if marker.startswith(pending):
            continue
        sys.stdout.write(pending)
        sys.stdout.flush()
        pending = ""
    if pending and not pending.startswith(marker):
        sys.stdout.write(pending)
    rc = proc.wait()
    output = "".join(collected)
    if rc:
        error(f"Fjernkommando mislykkedes ({rc})\n{output[-700:]}")
    return output


def ssh(name, command, capture=False, tty=False):
    host = BROKERS[name][0]
    args = ["ssh", "-tt" if tty else "-T", f"{SSH_USER}@{host}", command]
    return run(args, capture=capture, tty=tty)


def remotenode(name, *args, capture=False):
    # -tt lader sudo spørge om adgangskode på et interaktivt terminal-tty
    # Ingen klartekst MQTT-adgangskoder videregives som kommandolinje-parametre.
    command = "sudo python3 " + shlex.quote(REMOTE_SCRIPT) + " _node " + " ".join(shlex.quote(a) for a in args)
    return ssh(name, command, capture=capture, tty=True)


def remote_json(name, command, *args):
    output = remotenode(name, command, *args, capture=True)
    match = re.search(r"^MQTT_RESULT:(.*)$", output, re.MULTILINE)
    if not match:
        error(f"Uventet svar fra {name}: {output[-1000:]!r}")
    return json.loads(match.group(1).strip())


def deploy_helper():
    me = str(Path(__file__).resolve())
    for name, (ip, _) in BROKERS.items():
        print(f"Kontrollerer SSH til {name} ({ip}) ...", flush=True)
        ssh(name, f"mkdir -p {shlex.quote(REMOTE_DIR)} && chmod 700 {shlex.quote(REMOTE_DIR)}")
        run(["scp", "-q", me, f"{SSH_USER}@{ip}:{REMOTE_SCRIPT}"])
        ssh(name, f"chmod 600 {shlex.quote(REMOTE_SCRIPT)}")


def file_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def backup(path):
    if path.exists():
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = path.with_name(path.name + ".bak-mqtt-admin-" + suffix)
        shutil.copy2(path, backup_path)
        return str(backup_path)
    return None


def atomic_write(path, text):
    parent_stat = path.parent.stat()
    previous = path.stat() if path.exists() else None
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".mqtt-admin-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chown(tmp, previous.st_uid if previous else parent_stat.st_uid,
                 previous.st_gid if previous else parent_stat.st_gid)
        os.chmod(tmp, stat.S_IMODE(previous.st_mode) if previous else 0o640)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def user_entry_exists(content, username):
    return any(line.split(":", 1)[0] == username for line in content.splitlines() if ":" in line)


def acl_user_exists(content, username):
    return bool(re.search(r"^\s*user\s+" + re.escape(username) + r"\s*$", content, re.M))


def make_acl_block(username, pub, sub):
    lines = [f"{START_MARKER}{username}", f"user {username}"]
    lines += [f"topic write {t}" for t in pub]
    lines += [f"topic read {t}" for t in sub]
    lines += [f"{END_MARKER}{username}"]
    return "\n".join(lines) + "\n"


def update_acl(content, username, pub, sub, remove=False):
    start = f"{START_MARKER}{username}"
    end = f"{END_MARKER}{username}"
    oldlines = content.splitlines(keepends=True)
    begin = [i for i, s in enumerate(oldlines) if s.strip() == start]
    endpos = [i for i, s in enumerate(oldlines) if s.strip() == end]
    if len(begin) != len(endpos) or len(begin) > 1:
        error("Ugyldige eller dublerede MQTT managed ACL-markører")
    if begin:
        if begin[0] > endpos[0]:
            error("Forkert rækkefølge af ACL-markører")
        # Forhindr, at en efterfølgende u-markeret 'topic'-linje arver
        # den nuværende brugeridentitet ved en fremtidig ACL-opdatering.
        if endpos[0] + 1 < len(oldlines):
            tail = "".join(oldlines[endpos[0]+1:])
            if re.search(r"^\s*topic\s+", tail, re.M) and not re.search(r"^\s*user\s+", tail, re.M):
                error("ACL indeholder umarkerede topic-regler efter den administrerede blok")
        del oldlines[begin[0]:endpos[0] + 1]
    elif acl_user_exists(content, username):
        error("Brugeren har allerede en manuelt vedligeholdt ACL. Rediger manuelt først.")
    if not remove:
        existing = "".join(oldlines).rstrip("\n")
        new = make_acl_block(username, pub, sub)
        return (existing + "\n\n" if existing else "") + new
    return "".join(oldlines)


def node_main(argv):
    cmd = argv[0]
    passwd = ETC / "vmq.passwd"
    acl = ETC / "vmq.acl"
    if not ETC.is_dir():
        error(f"Konfigurationsmappen {ETC} findes ikke. Er bind mount korrekt?")
    if cmd == "status":
        username = argv[1]
        conf = file_text(ETC / "vernemq.conf")
        if not passwd.is_file():
            error(f"Passwordfil findes ikke: {passwd}")
        if not acl.is_file():
            error(f"ACL-fil findes ikke: {acl}. Kontrollér VerneMQ-konfigurationen.")
        res = {
            "passwd": user_entry_exists(file_text(passwd), username),
            "acl": acl_user_exists(file_text(acl), username),
            "plugins_acl_off": bool(re.search(r"^\s*plugins\.vmq_acl\s*=\s*off\s*$", conf, re.M)),
            "plugins_passwd_off": bool(re.search(r"^\s*plugins\.vmq_passwd\s*=\s*off\s*$", conf, re.M)),
            "has_patterns": bool(re.search(r"^\s*pattern\s+", file_text(acl), re.M)),
        }
        print("MQTT_RESULT:" + json.dumps(res))
    elif cmd == "hash":
        username = argv[1]
        matches = [l for l in file_text(passwd).splitlines()
                   if l.startswith(username + ":")]
        if len(matches) != 1:
            error("Forventede præcis én password-entry på master")
        print("MQTT_RESULT:" + json.dumps({"hash": matches[0]}))
    elif cmd == "apply":
        username, mode, pub64, sub64, sourcefile = argv[1:6]
        pub = json.loads(base64.b64decode(pub64).decode())
        sub = json.loads(base64.b64decode(sub64).decode())
        new_acl = update_acl(file_text(acl), username, pub, sub)
        hash_line = Path(sourcefile).read_text(encoding="utf-8").strip()
        if not hash_line.startswith(username + ":"):
            error("Modtaget passwordhash svarer ikke til brugeren")
        entries = file_text(passwd).splitlines()
        found = [i for i, line in enumerate(entries) if line.startswith(username + ":")]
        if len(found) > 1:
            error("Dubleret bruger i passwordfilen")
        if mode == "master":
            if len(found) != 1 or entries[found[0]] != hash_line:
                error("Masterpassword matcher ikke den nye password-entry")
        else:
            if found:
                entries[found[0]] = hash_line
            else:
                entries.append(hash_line)
            backup(passwd)
            atomic_write(passwd, "\n".join(entries) + "\n")
        backup(acl)
        atomic_write(acl, new_acl)
        try:
            os.remove(sourcefile)
        except FileNotFoundError:
            pass
        print("OK: bruger og ACL installeret")
    else:
        error(f"Ukendt remote handling: {cmd}")


def controller_add(username, pub, sub):
    deploy_helper()
    for name in BROKERS:
        info = remote_json(name, "status", username)
        if info["passwd"] or info["acl"]:
            error(f"{username!r} findes allerede på {name}. Stopper uden at ændre eksisterende rettigheder.")
        if info["plugins_acl_off"] or info["plugins_passwd_off"]:
            error(f"Filbaseret autentificering/autorisation er deaktiveret på {name}.")
        if info["has_patterns"]:
            error(f"ACL på {name} indeholder globale pattern-regler. Gennemgå dem manuelt før automatisk ACL-styring.")
    print("\nOpretter adgangskode via vmq-passwd på Node3.", flush=True)
    print("Indtast samme nye adgangskode to gange ved prompten.", flush=True)
    # TTY kræves af docker exec -it, adgangskoden bliver ikke del af argv eller historik.
    service = BROKERS[MASTER][1]
    command = ("CID=$(sudo docker ps -q -f " + shlex.quote("label=com.docker.swarm.service.name=" + service) + "); "
               "test -n \"$CID\" || exit 2; "
               "sudo docker exec -it \"$CID\" /vernemq/bin/vmq-passwd /vernemq/etc/vmq.passwd " + shlex.quote(username))
    ssh(MASTER, command, tty=True)
    hashline = remote_json(MASTER, "hash", username)["hash"]
    token_pub = base64.b64encode(json.dumps(pub).encode()).decode()
    token_sub = base64.b64encode(json.dumps(sub).encode()).decode()
    # scp til brugerens private administrationsmappe; hash er aldrig klartekst.
    with tempfile.TemporaryDirectory(prefix="mqtt-users-") as folder:
        localfile = Path(folder) / "passwd-entry"
        localfile.write_text(hashline + "\n", encoding="utf-8")
        localfile.chmod(0o600)
        for name in BROKERS:
            ip = BROKERS[name][0]
            remotehash = REMOTE_DIR + "/.hash-" + username
            run(["scp", "-q", str(localfile), f"{SSH_USER}@{ip}:{remotehash}"])
            remotenode(name, "apply", username, "master" if name == MASTER else "replica",
                       token_pub, token_sub, remotehash)
    print("\nOK. Bruger og ACL er oprettet på alle tre brokere.")
    print("Vent ca. 10 sekunder på VerneMQs filgenindlæsning, og test MQTT-login samt ACL.")


def main():
    parser = argparse.ArgumentParser(description="Opret MQTT-bruger og ACL på VerneMQ-clusteret")
    parser.add_argument("command", choices=["check", "add", "_node"])
    parser.add_argument("rest", nargs="*")
    parser.add_argument("--pub", action="append", default=[], metavar="TOPIC",
                        help="Topic som brugeren må publicere til; gentages efter behov")
    parser.add_argument("--sub", action="append", default=[], metavar="TOPIC",
                        help="Topic som brugeren må abonnere på; gentages efter behov")
    args = parser.parse_args()
    if args.command == "_node":
        node_main(args.rest)
        return
    if args.command == "check":
        if args.rest:
            parser.error("check tager ingen argumenter")
        deploy_helper()
        for name in BROKERS:
            info = remote_json(name, "status", "mqtt-admin-preflight-test")
            problems = []
            if info["plugins_acl_off"]:
                problems.append("ACL-plugin er slået fra")
            if info["plugins_passwd_off"]:
                problems.append("password-plugin er slået fra")
            if info["has_patterns"]:
                problems.append("globale pattern-regler findes; gennemgå ACL")
            print(f"{name}: " + ("; ".join(problems) if problems else "password-/ACL-filer fundet, ingen kendte blokeringer"))
        return
    if len(args.rest) != 1:
        parser.error("Brug: add BRUGER --pub TOPIC --sub TOPIC")
    username = args.rest[0]
    if not NAME_RE.fullmatch(username):
        parser.error("Brugernavn: små bogstaver og tal, _ eller -, skal begynde med bogstav")
    if not args.pub and not args.sub:
        parser.error("Mindst én --pub eller --sub er nødvendig")
    for t in args.pub + args.sub:
        validate_topic(t)
    controller_add(username, args.pub, args.sub)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as ex:
        print(f"FEJL: {ex}", file=sys.stderr)
        sys.exit(1)