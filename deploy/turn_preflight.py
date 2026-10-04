#!/usr/bin/env python3
"""Read-only checks before a TURN cutover; never starts/stops services."""

import argparse
import ipaddress
import json
import re
import socket
import subprocess
from pathlib import Path

from render_turn import PROJECT, domain, read_env, render


SUBNET = ipaddress.ip_network("172.30.249.0/29")
BASE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.media.yaml"]
TURN = BASE + ["-f", "compose.turn.yaml"]


def run(command):
    # Keep stderr/large config output private: Compose can include secrets in errors.
    result = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise ValueError(f"Command failed: {command[0]} {command[1]}. Inspect it privately on the server.")
    return result.stdout


def check_dns(host, expected):
    addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if addresses != {str(ipaddress.IPv4Address(expected))}:
        raise ValueError("TURN DNS must point ONLY to this IPv4 address; remove stale A/AAAA records.")


def check_networks(networks):
    for network in networks:
        for pool in network.get("IPAM", {}).get("Config", []) or []:
            value = pool.get("Subnet")
            if value and ipaddress.ip_network(value).version == 4 and SUBNET.overlaps(ipaddress.ip_network(value)):
                if network.get("Name") != "coursemc_turn-edge" or ipaddress.ip_network(value) != SUBNET:
                    raise ValueError("TURN subnet overlaps an existing Docker network; do not activate.")


def check_rooms():
    script = """
import json, os, time, urllib.request
import jwt
now = int(time.time())
token = jwt.encode({'iss': os.environ['LIVEKIT_API_KEY'], 'nbf': now, 'exp': now + 60,
                    'video': {'roomList': True}}, os.environ['LIVEKIT_API_SECRET'], algorithm='HS256')
url = os.environ.get('LIVEKIT_API_URL') or 'http://livekit:7880'
url = url.rstrip('/') + '/twirp/livekit.RoomService/ListRooms'
request = urllib.request.Request(url, b'{}', headers={
    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(request, timeout=10) as response:
    rooms = json.load(response).get('rooms', [])
print(sum(int(room.get('numParticipants', room.get('num_participants', 0))) for room in rooms))
"""
    count = int(run(BASE + ["exec", "-T", "web", "python", "-c", script]).strip())
    if count:
        raise ValueError(f"There are {count} connected participants. Wait until all lessons finish.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-ip", required=True)
    args = parser.parse_args()
    try:
        values = read_env(PROJECT / ".env")
        render(values.get("DOMAIN", ""), values.get("LIVEKIT_TURN_DOMAIN", ""))
        host = domain(values["LIVEKIT_TURN_DOMAIN"])
        check_dns(host, args.public_ip)
        version = run(["docker", "compose", "version", "--short"])
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match or tuple(map(int, match.groups())) < (2, 24, 4):
            raise ValueError("Docker Compose >= 2.24.4 is required for safe port override.")
        run(TURN + ["config", "--quiet"])
        ids = run(["docker", "network", "ls", "--quiet"]).split()
        check_networks(json.loads(run(["docker", "network", "inspect", *ids])))
        for name in (values["DOMAIN"], host):
            cert = PROJECT / "data/certbot/conf/live" / name / "fullchain.pem"
            if not cert.is_file():
                raise ValueError(f"Missing certificate for {name}.")
            run(["openssl", "x509", "-in", str(cert), "-noout", "-checkend", "86400"])
            output = run(["openssl", "x509", "-in", str(cert), "-noout", "-checkhost", name])
            if "does match" not in output:
                raise ValueError(f"Certificate hostname mismatch for {name}.")
        check_rooms()
        # A first activation adds this UDP range; existing TURN deployments own it already.
        running_edge = run(TURN + ["ps", "--status", "running", "--quiet", "media-edge"]).strip()
        if not running_edge:
            for port in range(40000, 40200):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.bind(("0.0.0.0", port))
        print("Preflight OK: DNS, certificates, Compose, subnet, ports; no active participants.")
        print("Also check host/provider firewalls and take a verified backup before activation.")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"TURN cutover blocked: {error}\n")


if __name__ == "__main__":
    main()
