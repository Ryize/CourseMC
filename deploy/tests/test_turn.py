"""Transport/config unit tests: python3 -m unittest discover -s deploy/tests."""

import hashlib
import hmac
import json
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_turn import (ALPHABET, COOKIE, DATA, ERROR, INTEGRITY, LIFETIME, NONCE, REALM,
                        RELAY, RelayClient, base62, credentials, decode_address, error_code,
                        message, parse, xor_address)
from render_turn import PROJECT, domain, read_env, render
from turn_preflight import check_dns, check_networks


class ConfigurationTests(unittest.TestCase):
    def test_separate_turn_and_unchanged_default_https(self):
        files = render("COURSEMC.RU", "TURN.COURSEMC.RU")
        self.assertIn("turn.coursemc.ru 127.0.0.1:8443;", files["edge.conf"])
        self.assertIn("default nginx:443;", files["edge.conf"])
        self.assertIn("ssl proxy_protocol", files["nginx/default.conf"])
        self.assertIn("set_real_ip_from 172.30.249.2;", files["nginx/default.conf"])
        self.assertIn("/livekit/", files["nginx/default.conf"])
        self.assertIn("listen 443 ssl;", (PROJECT / "deploy/nginx/https.conf.template").read_text())
        self.assertNotIn("load_module", files["edge.conf"])

    def test_invalid_hostnames_fail_closed(self):
        for host in ("", "https://turn.coursemc.ru", "*.coursemc.ru", "127.0.0.1",
                     "turn.coursemc.ru;", "turn..ru", "-turn.ru", "turn_.ru", "turn.ru\nkeys:x"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                domain(host)
        for turn in ("coursemc.ru", "www.coursemc.ru"):
            with self.assertRaises(ValueError):
                render("coursemc.ru", turn)

    def test_dotenv_does_not_execute_or_interpolate(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "input.env"
            target.write_text('DOMAIN="coursemc.ru"\nLIVEKIT_TURN_DOMAIN=turn.coursemc.ru\n'
                              'SECRET=$(do-not-execute)\n# COMMENT=ignored\n')
            values = read_env(target)
            self.assertEqual(values["DOMAIN"], "coursemc.ru")
            self.assertEqual(values["SECRET"], "$(do-not-execute)")
            self.assertNotIn("# COMMENT", values)

    def test_check_mode_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / "input.env"
            env.write_text("DOMAIN=coursemc.ru\nLIVEKIT_TURN_DOMAIN=turn.coursemc.ru\n")
            output = Path(folder) / "output"
            result = subprocess.run([sys.executable, str(PROJECT / "deploy/render_turn.py"),
                                     "--env-file", str(env), "--output", str(output), "--check"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(output.exists())

    @patch("turn_preflight.socket.getaddrinfo")
    def test_dns_rejects_wrong_or_stale_addresses(self, lookup):
        lookup.return_value = [(None, None, None, None, ("201.51.5.223", 443))]
        check_dns("turn.coursemc.ru", "201.51.5.223")
        for ip in ("203.0.113.1", "::1"):
            lookup.return_value.append((None, None, None, None, (ip, 443)))
            with self.assertRaises(ValueError):
                check_dns("turn.coursemc.ru", "201.51.5.223")

    def test_subnet_collision_is_blocked(self):
        def network(name, subnet):
            return {"Name": name, "IPAM": {"Config": [{"Subnet": subnet}]}}
        check_networks([network("other", "172.19.0.0/16")])
        check_networks([network("coursemc_turn-edge", "172.30.249.0/29")])
        with self.assertRaises(ValueError):
            check_networks([network("other", "172.30.0.0/16")])
        with self.assertRaises(ValueError):
            check_networks([network("coursemc_turn-edge", "172.30.0.0/16")])

    def test_compose_merge_exposes_only_one_public_443(self):
        environment = dict(os.environ, LIVEKIT_API_KEY="turn-test-key",
                           LIVEKIT_API_SECRET="test-only-not-a-production-secret-32-plus",
                           LIVEKIT_TURN_DOMAIN="turn.coursemc.ru")
        try:
            result = subprocess.run(["docker", "compose", "--env-file", ".env.example",
                                     "-f", "compose.yaml", "-f", "compose.media.yaml", "-f", "compose.turn.yaml",
                                     "config", "--format", "json"], cwd=PROJECT, env=environment,
                                    capture_output=True, text=True, timeout=20)
        except FileNotFoundError:
            self.skipTest("Docker Compose is not installed")
        self.assertEqual(result.returncode, 0, "Compose config validation failed (output kept private)")
        services = json.loads(result.stdout)["services"]
        public_443 = [(name, port) for name, service in services.items()
                      for port in service.get("ports", []) if str(port.get("published")) == "443"]
        self.assertEqual([name for name, _ in public_443], ["media-edge"])
        self.assertEqual([str(p["published"]) for p in services["nginx"]["ports"]], ["80"])
        self.assertTrue(any(str(p["published"]) == "7882" for p in services["livekit"]["ports"]))
        mounts = {v["target"]: v["source"] for v in services["nginx"]["volumes"]}
        self.assertTrue(mounts["/etc/nginx/conf.d"].endswith("runtime/turn/nginx"))
        config = services["livekit"]["environment"]["LIVEKIT_CONFIG"]
        for setting in ("tls_port: 443", "external_tls: true", "proxy_protocol: true", "ttl_seconds: 300"):
            self.assertIn(setting, config)
        self.assertNotIn("allow_restricted_peer_cidrs", config)


class ProtocolTests(unittest.TestCase):
    def test_base62_bit_encoding_roundtrip(self):
        # Independent decode verifies 5-bit compact digits and leading zero bytes.
        def decode(text):
            result, cursor = 0, 0
            for index, char in enumerate(text):
                digit = ALPHABET.index(char)
                result |= digit << cursor
                cursor += (digit.bit_length() if index == len(text) - 1
                           else 5 if digit & 0x1E == 0x1E else 6)
            return result.to_bytes((cursor + 7) // 8, "big")
        rng = random.Random(9)
        for size in range(1, 80):
            for data in (b"\0" * size, b"\xff" * size, rng.randbytes(size)):
                self.assertEqual(decode(base62(data)), data)
        self.assertEqual(base62(b""), "")
        self.assertEqual(base62(b"\xff"), "fH")

    def test_livekit_temporary_credentials_are_deterministic_and_distinct(self):
        first = credentials("key", "secret", "participant-a", 2000000000)
        self.assertEqual(first, credentials("key", "secret", "participant-a", 2000000000))
        self.assertNotEqual(first, credentials("key", "secret", "participant-b", 2000000000))
        self.assertNotEqual(first, credentials("key", "secret", "participant-a", 2000000001))

    def test_integrity_uses_length_including_integrity_attribute(self):
        packet = message(3, [(LIFETIME, struct.pack("!I", 60))], b"key", b"123456789012")
        self.assertEqual(len(packet) - 20, struct.unpack("!H", packet[2:4])[0])
        expected = hmac.new(b"key", packet[:-24], hashlib.sha1).digest()
        self.assertEqual(packet[-20:], expected)
        self.assertEqual(parse(packet)[2][INTEGRITY], expected)

    def test_padding_and_xor_addresses(self):
        packet = message(0x17, [(DATA, b"hello")], transaction=b"123456789012")
        self.assertEqual(parse(packet)[2][DATA], b"hello")
        for address in (("201.51.5.223", 40005), ("2001:db8::1234", 50001)):
            value = xor_address(address, b"123456789012")
            self.assertEqual(decode_address(value, b"123456789012"), address)

    def test_malformed_packets_are_rejected(self):
        for packet in (b"", b"\0" * 20, struct.pack("!HHI12s", 3, 4, COOKIE, b"0" * 12),
                       message(3, []) + b"extra", message(3, [])[:19],
                       struct.pack("!HHI12sHH", 3, 4, COOKIE, b"0" * 12, DATA, 20)):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                parse(packet)

    def test_unauthenticated_or_failed_allocations_cannot_pass(self):
        client = RelayClient.__new__(RelayClient)
        client.username, client.password, client.allocated = b"test", "test", False
        with patch.object(client, "request", return_value={RELAY: b"bad"}):
            with self.assertRaises(ValueError):
                client.allocate()
        challenge = {ERROR: b"\0\0\x04\x01", REALM: b"livekit", NONCE: b"nonce"}
        self.assertEqual(error_code(challenge), 401)
        with patch.object(client, "request", side_effect=[challenge, challenge]):
            with self.assertRaises(ValueError):
                client.allocate()
        self.assertFalse(client.allocated)


if __name__ == "__main__":
    unittest.main()
