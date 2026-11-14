"""Verify repair of the observed split and rejection of ambiguous neighbors."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from shelly_fixtures import BODY, pair, record

MODULE = Path(__file__).resolve().parents[1] / "resources/syslogng/python/shelly_fragments.py"
SPEC = importlib.util.spec_from_file_location("shelly_fragments", MODULE)
fragments = importlib.util.module_from_spec(SPEC)
# The real LogParser bridge is exercised by E2E; offline tests need no installed
# syslog-ng Python bindings and exercise the same production implementation.
with patch.dict("sys.modules", {"syslogng": SimpleNamespace(LogParser=object)}):
    SPEC.loader.exec_module(fragments)


class FragmentTests(unittest.TestCase):
    def test_observed_split_and_surrounding_records(self):
        self.assertTrue(BODY[:128].endswith(b'"ev'))
        before = record(b"independent", seq=9)
        after = record(b"independent", seq=12)
        payload = before + b"\0\0" + pair() + b"\0" + after + b"\0"
        self.assertEqual(
            fragments.reassemble(payload),
            before + b"\0\0" + record(BODY) + b"\0" + after + b"\0",
        )

    def test_header_boundaries(self):
        for change in (
            {"device": "shelly-other"},
            {"uptime": "123.458"},
            {"channel": 101},
            {"level": 1},
        ):
            with self.subTest(change=change):
                payload = pair(**change)
                self.assertEqual(fragments.reassemble(payload), payload)
        for seq in (9, 10, 12, 0):
            payload = record(BODY[:128]) + b"\0" + record(BODY[128:], seq=seq)
            self.assertEqual(fragments.reassemble(payload), payload)

    def test_boundary_within_each_part_of_event_key(self):
        stamp = b"1789336808.31453800201"
        for delta in (-3, -2, -1, 0, 1):
            replacement = stamp[:delta] if delta < 0 else stamp + b"0" * delta
            body = BODY.replace(stamp, replacement)
            self.assertEqual(fragments.reassemble(pair(body)), record(body))

    def test_one_forward_millisecond_is_repaired(self):
        for start, end in (
            ("123.456", "123.457"),
            ("123.999", "124.000"),
            ("825983.239", "825983.240"),
            ("190176.509", "190176.510"),
        ):
            with self.subTest(start=start, end=end):
                first = record(BODY[:128], uptime=start)
                second = record(BODY[128:], seq=11, uptime=end)
                self.assertEqual(
                    fragments.reassemble(first + b"\0" + second), record(BODY, uptime=start)
                )

    def test_backwards_larger_or_unknown_time_gaps_are_not_joined(self):
        for uptime in ("123.455", "123.458", "124.456", "0.000", "123.4571"):
            payload = pair(uptime=uptime)
            self.assertEqual(fragments.reassemble(payload), payload)

    def test_clock_tolerance_does_not_join_independent_text_or_other_devices(self):
        for payload in (
            pair(device="shelly-other", uptime="123.457"),
            record(b"x" * 128) + b"\0" + record(b"independent", seq=11, uptime="123.457"),
            record(BODY[:128]) + b"\0" + record(BODY[128:], seq=12, uptime="123.457"),
        ):
            self.assertEqual(fragments.reassemble(payload), payload)

    def test_never_buffers_across_datagrams_or_skips_delimiters(self):
        first, second = pair().split(b"\0")
        for payload in (first, second, second + b"\0" + first, first + b"\0\0" + second):
            self.assertEqual(fragments.reassemble(payload), payload)

    def test_independent_and_incomplete_messages_remain_exact(self):
        for neighbor in (
            b"entirely independent",
            BODY,
            b"ch type=WS_in has no DST",
            b'{"event":"power_measurement"}',
            BODY[128:-1],
            BODY[128:] + b"trailing text",
        ):
            payload = record(BODY[:128]) + b"\0" + record(neighbor, seq=11)
            self.assertEqual(fragments.reassemble(payload), payload)
        payload = record(b"x" * 128) + b"\0" + record(b"continuation", seq=11)
        self.assertEqual(fragments.reassemble(payload), payload)

    def test_inconsistent_or_nonstandard_json_is_not_joined(self):
        for body in (
            BODY.replace(b'"info":{"component":"switch:0"', b'"info":{"component":"switch:1"'),
            BODY.replace(
                b'"info":{"component":"switch:0","id":0', b'"info":{"component":"switch:0","id":1'
            ),
            BODY.replace(b'"apower":0', b'"apower":NaN'),
            BODY.replace(b'"apower":0', b'"apower":1e999'),
            BODY.replace(b'"apower":0', b'"apower":true'),
            BODY.replace(b'"apower":0', b'"apower":0,"apower":1'),
            BODY.replace(b'"apower":0', b'"extra":1,"apower":0'),
            BODY.replace(b'"ts":1789336808.30999994277', b'"id":1,"ts":1'),
        ):
            payload = pair(body)
            self.assertEqual(fragments.reassemble(payload), payload)

    def test_complete_128_byte_message_is_not_a_fragment(self):
        body = b"raw-event: " + b'{"event":"independent"}'
        body += b" " * (128 - len(body))
        payload = record(body) + b"\0" + record(BODY[128:], seq=11)
        self.assertEqual(fragments.reassemble(payload), payload)

    def test_length_and_unknown_headers(self):
        for payload in (
            pair().replace(b"raw-event:", b"raw-event: "),
            pair().replace(b" 102 ", b" 101 "),
            pair().replace(b" 10 ", b" 9999999999999999999999999999 "),
            b"\xff\0" + pair(),
        ):
            if payload.startswith(b"\xff"):
                self.assertEqual(fragments.reassemble(payload), b"\xff\0" + record(BODY))
            else:
                self.assertEqual(fragments.reassemble(payload), payload)

    def test_adapter_keeps_records_on_rejection(self):
        parser = fragments.ShellyFragments()
        message = {"MESSAGE": pair()}
        self.assertTrue(parser.parse(message))
        self.assertEqual(message["MESSAGE"], record(BODY))
        message = {"MESSAGE": b"unrecognized\0raw bytes\xff  "}
        self.assertTrue(parser.parse(message))
        self.assertEqual(message["MESSAGE"], b"unrecognized\0raw bytes\xff  ")


if __name__ == "__main__":
    unittest.main()
