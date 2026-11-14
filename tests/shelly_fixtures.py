"""Synthetic wire examples of the observed 128-byte power-event split."""

BODY = (
    b'raw-event: {"component":"switch:0","name":"switch","id":0,'
    b'"now":1789336808.31453800201,"info":{"component":"switch:0","id":0,'
    b'"event":"power_measurement","apower":0,"ts":1789336808.30999994277}}'
)


def record(body, seq=10, device="shelly-test", uptime="123.456", channel=102, level=2):
    return f"{device} {seq} {uptime} {channel} {level}|".encode() + body


def pair(body=BODY, **changes):
    return record(body[:128]) + b"\0" + record(body[128:], seq=11, **changes)
