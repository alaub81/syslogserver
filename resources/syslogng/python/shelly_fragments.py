"""Conservative, stateless repair of Shelly power-measurement UDP records.

There is no continuation flag in the wire protocol. Only repair the observed
128-byte split inside the JSON key "event"; never infer joins from length alone.
"""

import json
import math
import re

from syslogng import LogParser

HEADER = re.compile(
    rb"^(?P<device>shelly[\w.-]+) +(?P<seq>[0-9]{1,20}) +"
    rb"(?P<uptime>[0-9]+(?:\.[0-9]+)?) +(?P<channel>102) +"
    rb"(?P<level>[0-4])\|(?P<body>[\s\S]*)$"
)
PREFIX = b"raw-event: "
SPLIT_KEY = re.compile(rb'"(e|ev|eve|even|event)$')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def adjacent_uptime(first, second):
    """A fragment pair may straddle one forward millisecond clock tick.

    Use integer milliseconds, not rounded floats. Unknown precision, backwards
    clocks and larger gaps remain separate. This is not a buffering timeout.
    """
    if first == second:
        return True

    def milliseconds(value):
        whole, _, fraction = value.partition(b".")
        if len(whole) > 20 or len(fraction) > 3:
            return None
        return int(whole) * 1000 + int(fraction.ljust(3, b"0"))

    start, end = milliseconds(first), milliseconds(second)
    return start is not None and end is not None and 0 <= end - start <= 1


def measurement(body):
    """Require the known event schema, including consistent nested identity."""
    try:
        event = json.loads(body[len(PREFIX) :], object_pairs_hook=unique_object)
        if not isinstance(event, dict) or set(event) != {"component", "name", "id", "now", "info"}:
            return False
        info = event["info"]
        if not isinstance(info, dict) or set(info) != {"component", "id", "event", "apower", "ts"}:
            return False
        return (
            event["name"] == "switch"
            and type(event["id"]) is int
            and event["id"] >= 0
            and event["component"] == f"switch:{event['id']}"
            and info["component"] == event["component"]
            and type(info["id"]) is int
            and info["id"] == event["id"]
            and info["event"] == "power_measurement"
            and all(number(value) for value in (event["now"], info["apower"], info["ts"]))
        )
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        return False


def reassemble(payload):
    """Only adjacent records in this single datagram can be joined.

    Preserve every byte, including delimiters, on any rejected candidate.
    No buffers survive a call, so loss, reordering, reloads and other senders
    cannot accidentally complete an earlier message.
    """
    records = payload.split(b"\0")
    index = 0
    while index + 1 < len(records):
        first = HEADER.fullmatch(records[index])
        second = HEADER.fullmatch(records[index + 1])
        if first and second:
            body = first["body"]
            key = SPLIT_KEY.search(body)
            if (
                len(body) == 128
                and body.startswith(PREFIX + b'{"component":')
                and key
                and all(first[field] == second[field] for field in ("device", "channel", "level"))
                and adjacent_uptime(first["uptime"], second["uptime"])
                and int(second["seq"]) == int(first["seq"]) + 1
                and 0 < len(second["body"]) <= 128
                and second["body"].startswith(b"event"[len(key[1]) :] + b'":"power_measurement",')
                and measurement(body + second["body"])
            ):
                records[index] += second["body"]
                del records[index + 1]
        index += 1
    return b"\0".join(records)


class ShellyFragments(LogParser):
    def parse(self, message):
        original = message["MESSAGE"]
        repaired = reassemble(original)
        if repaired != original:
            message["MESSAGE"] = repaired
        return True
