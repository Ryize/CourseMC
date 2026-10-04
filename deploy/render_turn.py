#!/usr/bin/env python3
"""Render the optional TURN edge, leaving normal HTTPS/secret files untouched."""

import argparse
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
EDGE_IP = "172.30.249.2"


def read_env(path):
    """Small dotenv reader for literal values; never executes/interpolates content."""
    values = {}
    for line in Path(path).read_text().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            value = value.strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def domain(value):
    value = value.lower()
    labels = value.split(".")
    if len(value) > 253 or len(labels) < 2 or not re.fullmatch(r"[a-z]{2,63}", labels[-1]):
        raise ValueError("A literal DNS hostname is required, not a URL/IP/wildcard.")
    for label in labels:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label):
            raise ValueError("Invalid DNS hostname.")
    return value


def render(site_domain, turn_domain):
    site_domain, turn_domain = domain(site_domain), domain(turn_domain)
    if turn_domain in (site_domain, "www." + site_domain):
        raise ValueError("TURN needs its own hostname, separate from the website.")
    website = (PROJECT / "deploy/nginx/https.conf.template").read_text()
    website = website.replace("__DOMAIN__", site_domain)
    for old in ("listen 443 ssl;", "listen [::]:443 ssl;"):
        if website.count(old) != 1:
            raise ValueError("HTTPS template changed; review the TURN proxy integration.")
        website = website.replace(old, old.replace(" ssl;", " ssl proxy_protocol;"))
    website = website.replace("    http2 on;", (
        "    http2 on;\n"
        f"    set_real_ip_from {EDGE_IP};\n"
        "    real_ip_header proxy_protocol;"
    ))
    acme = (
        "server {\n    listen 80;\n    listen [::]:80;\n"
        f"    server_name {turn_domain};\n"
        "    location /.well-known/acme-challenge/ { root /var/www/certbot; }\n"
        "    location / { return 404; }\n}\n"
    )
    edge = (PROJECT / "deploy/nginx/turn-edge.conf.template").read_text()
    edge = edge.replace("__TURN_DOMAIN__", turn_domain)
    return {"edge.conf": edge, "nginx/default.conf": website + "\n" + acme, "acme.conf": acme}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env")
    parser.add_argument("--output", type=Path, default=PROJECT / "runtime/turn")
    parser.add_argument("--check", action="store_true", help="validate only; write nothing")
    parser.add_argument("--print-domain", action="store_true", help="print only the public TURN hostname")
    args = parser.parse_args()
    try:
        values = read_env(args.env_file)
        files = render(values.get("DOMAIN", ""), values.get("LIVEKIT_TURN_DOMAIN", ""))
        if args.print_domain:
            print(domain(values["LIVEKIT_TURN_DOMAIN"]))
            return
        if not args.check:
            for relative, content in files.items():
                target = args.output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        print("TURN configuration validated." if args.check else "TURN configuration rendered; not activated.")
    except (OSError, ValueError) as error:
        parser.exit(1, f"TURN configuration rejected: {error}\n")


if __name__ == "__main__":
    main()
