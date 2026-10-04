#!/usr/bin/env python3
"""Check LiveKit v1.13.7 TURN/TLS auth and bidirectional relay, without a lesson.

Reads server credentials locally, creates two 60-second diagnostic credentials,
never prints them, checks a trusted TLS certificate, and releases allocations.
This is a transport check, not a substitute for a browser call with a real VPN.
"""

import argparse
import hashlib
import hmac
import ipaddress
import secrets
import socket
import ssl
import struct
import time
from contextlib import ExitStack
from pathlib import Path

from render_turn import PROJECT, domain, read_env


COOKIE = 0x2112A442
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
USERNAME, INTEGRITY, ERROR, LIFETIME = 0x0006, 0x0008, 0x0009, 0x000D
PEER, DATA, REALM, NONCE, RELAY, TRANSPORT = 0x0012, 0x0013, 0x0014, 0x0015, 0x0016, 0x0019


def base62(data):
    # jxskiss/base62 bit encoding (not an integer base conversion).
    value, remaining, output = int.from_bytes(data, "big"), len(data) * 8, []
    while remaining > 0:
        digit = value & ((1 << min(remaining, 6)) - 1)
        width = 6
        if digit & 0x1E == 0x1E:
            if remaining > 6 or digit > 0x1F:
                width = 5
            digit &= 0x1F
        output.append(ALPHABET[digit])
        value >>= width
        remaining -= width
    return "".join(output)


def credentials(api_key, secret, participant, expiry):
    username = base62(f"{api_key}|{participant}|{expiry}".encode())
    password = base62(hashlib.sha256(f"{secret}|{participant}|{expiry}".encode()).digest())
    return username, password


def attribute(kind, value):
    return struct.pack("!HH", kind, len(value)) + value + b"\0" * (-len(value) % 4)


def message(kind, attributes, key=None, transaction=None):
    transaction = transaction or secrets.token_bytes(12)
    body = b"".join(attribute(kind, value) for kind, value in attributes)
    header = struct.pack("!HHI12s", kind, len(body) + (24 if key else 0), COOKIE, transaction)
    if key:
        body += attribute(INTEGRITY, hmac.new(key, header + body, hashlib.sha1).digest())
    return header + body


def parse(packet):
    if len(packet) < 20:
        raise ValueError("Truncated TURN message.")
    kind, length, cookie, transaction = struct.unpack("!HHI12s", packet[:20])
    if cookie != COOKIE or len(packet) != 20 + length or length % 4:
        raise ValueError("Invalid TURN frame.")
    attributes, cursor = {}, 20
    while cursor < len(packet):
        if cursor + 4 > len(packet):
            raise ValueError("Truncated TURN attribute.")
        attribute_kind, size = struct.unpack("!HH", packet[cursor:cursor + 4])
        cursor += 4
        end = cursor + size
        if end > len(packet):
            raise ValueError("Invalid TURN attribute length.")
        attributes[attribute_kind] = packet[cursor:end]
        cursor = end + (-size % 4)
    return kind, transaction, attributes


def error_code(attributes):
    error = attributes.get(ERROR, b"")
    return error[2] * 100 + error[3] if len(error) >= 4 else None


def xor_address(address, transaction=b"\0" * 12):
    ip, port = address
    packed = ipaddress.ip_address(ip).packed
    mask = struct.pack("!I", COOKIE) + transaction
    return struct.pack("!BBH", 0, 1 if len(packed) == 4 else 2, port ^ (COOKIE >> 16)) + bytes(
        value ^ mask[index] for index, value in enumerate(packed))


def decode_address(value, transaction):
    if len(value) not in (8, 20) or value[1] != (1 if len(value) == 8 else 2):
        raise ValueError("Invalid relay address.")
    mask = struct.pack("!I", COOKIE) + transaction
    ip = str(ipaddress.ip_address(bytes(v ^ mask[i] for i, v in enumerate(value[4:]))))
    return ip, struct.unpack("!H", value[2:4])[0] ^ (COOKIE >> 16)


class RelayClient:
    def __init__(self, context, hostname, connect_host, port, username, password):
        transport = socket.create_connection((connect_host, port), timeout=10)
        try:
            self.socket = context.wrap_socket(transport, server_hostname=hostname)
        except Exception:
            transport.close()
            raise
        self.username, self.password = username.encode(), password
        self.realm = self.nonce = self.key = None
        self.allocated = False

    def receive(self):
        def read_exact(length):
            output = bytearray()
            while len(output) < length:
                data = self.socket.recv(length - len(output))
                if not data:
                    raise ValueError("TURN connection closed.")
                output.extend(data)
            return bytes(output)
        header = read_exact(20)
        return parse(header + read_exact(struct.unpack("!H", header[2:4])[0]))

    def request(self, kind, attributes, authenticated=True):
        extra = ([(USERNAME, self.username), (REALM, self.realm), (NONCE, self.nonce)]
                 if authenticated else [])
        packet = message(kind, attributes + extra, self.key if authenticated else None)
        self.socket.sendall(packet)
        response, transaction, values = self.receive()
        if transaction != packet[8:20] or response not in (kind | 0x100, kind | 0x110):
            raise ValueError("Unexpected TURN response.")
        return values

    def allocate(self):
        attributes = [(TRANSPORT, b"\x11\0\0\0"), (LIFETIME, struct.pack("!I", 60))]
        challenge = self.request(0x0003, attributes, authenticated=False)
        if error_code(challenge) != 401 or not challenge.get(REALM) or not challenge.get(NONCE):
            raise ValueError("TURN must reject unauthenticated allocations with a challenge.")
        self.realm, self.nonce = challenge[REALM], challenge[NONCE]
        self.key = hashlib.md5(self.username + b":" + self.realm + b":" + self.password.encode()).digest()
        response = self.request(0x0003, attributes)
        if ERROR in response or RELAY not in response:
            raise ValueError(f"Authenticated TURN allocation failed ({error_code(response)}).")
        self.allocated = True
        # IPv4 relay addresses do not depend on the transaction ID.
        self.address = decode_address(response[RELAY], b"\0" * 12)
        if ipaddress.ip_address(self.address[0]).version != 4:
            raise ValueError("This deployment checker expects an IPv4 relay.")

    def permit(self, address):
        return self.request(0x0008, [(PEER, xor_address(address))])

    def send(self, address, payload):
        self.socket.sendall(message(0x0016, [(PEER, xor_address(address)), (DATA, payload)]))

    def expect(self, payload):
        kind, _, values = self.receive()
        if kind != 0x0017 or values.get(DATA) != payload:
            raise ValueError("TURN relay did not deliver the expected payload.")

    def close(self):
        try:
            if self.allocated:
                self.request(0x0004, [(LIFETIME, struct.pack("!I", 0))])
        except (OSError, ValueError):
            pass  # A failed connection still expires after at most 60 seconds.
        finally:
            self.socket.close()


def probe(hostname, api_key, api_secret, *, connect_host=None, port=443, cafile=None):
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with ExitStack() as stack:
        clients = []
        expiry = int(time.time()) + 60
        for _ in range(2):
            username, password = credentials(api_key, api_secret, "turn-check-" + secrets.token_hex(8), expiry)
            client = RelayClient(context, hostname, connect_host or hostname, port, username, password)
            stack.callback(client.close)
            client.allocate()
            clients.append(client)
        first, second = clients
        if not error_code(first.permit(("127.0.0.1", 80))):
            raise ValueError("TURN unexpectedly allows access to loopback peers.")
        for sender, receiver in ((first, second), (second, first)):
            if ERROR in sender.permit(receiver.address):
                raise ValueError("TURN rejected the diagnostic peer permission.")
        for sender, receiver in ((first, second), (second, first)):
            payload = b"coursemc-turn-check-" + secrets.token_bytes(32)
            sender.send(receiver.address, payload)
            receiver.expect(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env")
    parser.add_argument("--connect-ip", help="optional address; TLS still verifies the TURN hostname")
    args = parser.parse_args()
    try:
        values = read_env(args.env_file)
        host = domain(values.get("LIVEKIT_TURN_DOMAIN", ""))
        key, secret = values.get("LIVEKIT_API_KEY", ""), values.get("LIVEKIT_API_SECRET", "")
        if not key or len(secret) < 32:
            raise ValueError("Valid LiveKit credentials are required in the server env file.")
        if args.connect_ip:
            ipaddress.IPv4Address(args.connect_ip)
        probe(host, key, secret, connect_host=args.connect_ip)
        print("TURN/TLS OK: trusted TLS, authenticated allocations, blocked loopback, bidirectional relay.")
        print("Next: verify a real browser call from an external network with and without VPN.")
    except (OSError, ValueError) as error:
        parser.exit(1, f"TURN check failed: {error}\n")


if __name__ == "__main__":
    main()
