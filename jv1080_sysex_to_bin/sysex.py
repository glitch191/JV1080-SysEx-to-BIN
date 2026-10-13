"""Read JV-1080 patches from SysEx dumps (.syx) and Standard MIDI Files (.mid).

A JV-1080 patch is sent as Roland DT1 messages (model ID 6A, shared by the JV-2080, XP-50 / 60 / 80
and JV-1010): one Patch Common block (72 bytes, 73 on later models) and four Tone blocks
(129 bytes), in 7-bit address space:

    11 nn 00 00   user patch nn (00-7F), common     21 nn 00 00   data card patch nn
    11 nn 10 00   tone 1 (12 00, 14 00, 16 00: tones 2-4)
    03 00 00 00   temporary patch (patch mode)      02 pp 00 00   temporary patch of performance part pp

The data of every DT1 message is written into a sparse memory image, then complete patches
(common + four tones) are read back in address order: user, card, temporary, performance parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MODEL_ID = 0x6A
COMMON_SIZE = 0x48       # JV-1080; later models add one byte, ignored
TONE_SIZE = 0x81
TONE_OFFSETS = tuple(o << 7 for o in (0x10, 0x12, 0x14, 0x16))


def _a(b1: int, b2: int = 0) -> int:
    return (b1 << 21) | (b2 << 14)


# (label, base address of the first patch, number of patches); patches are 1 << 14 apart.
PATCH_AREAS = (
    ("User", _a(0x11), 128),
    ("Card", _a(0x21), 128),
    ("Temporary", _a(0x03), 1),
    ("Part", _a(0x02), 16),
)
RHYTHM_AREAS = ((_a(0x10, 0x40), 2), (_a(0x20, 0x40), 2), (_a(0x02, 0x09), 1))
PERFORMANCE_AREAS = ((_a(0x10), 32), (_a(0x20), 32), (_a(0x01), 1))


@dataclass
class Patch:
    common: bytes            # 72 bytes (Patch Common)
    tones: list[bytes]       # 4 x 129 bytes
    source: str = ""         # "User 001", "Card 012", "Temporary"...

    @property
    def name(self) -> str:
        return self.common[:12].decode("latin-1").rstrip()


@dataclass
class Dump:
    patches: list[Patch] = field(default_factory=list)
    rhythm_sets: int = 0
    performances: int = 0
    checksum_errors: int = 0
    messages: int = 0        # JV DT1 messages read


# --------------------------------------------------------------------------- containers

def sysex_messages(data: bytes) -> list[bytes]:
    """Every F0..F7 message in a raw byte stream (.syx); a message cut short by a new F0 is
    dropped."""
    out = []
    start = data.find(b"\xF0")
    while start >= 0:
        end = data.find(b"\xF7", start + 1)
        if end < 0:
            break
        nxt = data.find(b"\xF0", start + 1, end)
        if nxt >= 0:
            start = nxt
            continue
        out.append(data[start:end + 1])
        start = data.find(b"\xF0", end + 1)
    return out


def _varlen(data: bytes, i: int) -> tuple[int, int]:
    value = 0
    while True:
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, i


def smf_sysex(data: bytes) -> list[bytes]:
    """SysEx messages of a Standard MIDI File, all tracks in file order. A message split over
    several events (F0 then F7 continuation packets) is joined."""
    if data[:4] != b"MThd":
        raise ValueError("not a Standard MIDI File")
    out: list[bytes] = []
    pos = 8 + int.from_bytes(data[4:8], "big")
    while pos + 8 <= len(data):
        kind, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], "big")
        track, pos = data[pos + 8:pos + 8 + size], pos + 8 + size
        if kind != b"MTrk":
            continue
        i, status, pending = 0, 0, b""
        try:
            while i < len(track):
                _, i = _varlen(track, i)  # delta time
                b = track[i]
                if b == 0xFF:  # meta event: type, length, data
                    length, i = _varlen(track, i + 2)
                    i += length
                elif b in (0xF0, 0xF7):
                    length, j = _varlen(track, i + 1)
                    chunk, i = track[j:j + length], j + length
                    pending = b"\xF0" + chunk if b == 0xF0 else pending + chunk
                    if pending.endswith(b"\xF7"):
                        out.append(pending)
                        pending = b""
                else:
                    if b & 0x80:
                        status, i = b, i + 1
                    elif not status:
                        break  # data byte without a status: give up on this track
                    i += 1 if (status & 0xF0) in (0xC0, 0xD0) else 2
        except IndexError:
            pass  # truncated track: keep what was read
    return out


def read_messages(data: bytes) -> list[bytes]:
    return smf_sysex(data) if data[:4] == b"MThd" else sysex_messages(data)


# --------------------------------------------------------------------------- JV data

def jv_memory(messages: list[bytes]) -> tuple[dict[int, int], int, int]:
    """Sparse memory image from the JV DT1 messages: {address: byte}, message count, checksum
    errors (bad messages are still used: the data is usually fine)."""
    mem: dict[int, int] = {}
    count = errors = 0
    for m in messages:
        if len(m) < 12 or m[1] != 0x41 or m[3] != MODEL_ID or m[4] != 0x12:
            continue
        body = m[5:-2]
        if (sum(body) + m[-2]) & 0x7F:
            errors += 1
        # 7-bit address fields packed 7 bits apart: plain addition carries from byte to byte.
        address = (body[0] << 21) | (body[1] << 14) | (body[2] << 7) | body[3]
        for k, value in enumerate(body[4:]):
            mem[address + k] = value
        count += 1
    return mem, count, errors


def _block(mem: dict[int, int], base: int, size: int) -> bytes | None:
    values = [mem.get(base + k) for k in range(size)]
    return None if None in values else bytes(values)


def parse(data: bytes) -> Dump:
    """Patches (and counts of what is ignored) in the bytes of a .syx or .mid file."""
    mem, count, errors = jv_memory(read_messages(data))
    dump = Dump(messages=count, checksum_errors=errors)
    if not mem:
        return dump
    starts = {a >> 14 for a in mem}  # (first two address bytes) of every block present
    for label, base, n in PATCH_AREAS:
        for index in range(n):
            pbase = base + (index << 14)
            if pbase >> 14 not in starts:
                continue
            common = _block(mem, pbase, COMMON_SIZE)
            tones = [_block(mem, pbase + off, TONE_SIZE) for off in TONE_OFFSETS]
            if common is None or None in tones:
                continue
            source = label if n == 1 else f"{label} {index + 1:03d}" if n > 16 else f"{label} {index + 1}"
            dump.patches.append(Patch(common, tones, source))
    for base, n in RHYTHM_AREAS:
        dump.rhythm_sets += sum((base + (i << 14)) >> 14 in starts for i in range(n))
    for base, n in PERFORMANCE_AREAS:
        dump.performances += sum(_block(mem, base + (i << 14), 12) is not None
                                 and (base + (i << 14)) >> 14 in starts for i in range(n))
    return dump


def read_file(path: str) -> Dump:
    with open(path, "rb") as f:
        return parse(f.read())
