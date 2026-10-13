"""The plug-in's bank file (.bin): a 25-byte header, then 128 records of 23,255 bytes.

    "KoaBankFile00003" + "PG-JV1080" + 128 x record (patch or rhythm set)

Converted records are built on a template: a factory patch read from the plug-in's own banks
(installed with it, in Common Files\\VST3\\Roland\\JV-1080\\Patch), so no Roland data ships with
this tool.
"""

from __future__ import annotations

import os

from .patch import RECORD_SIZE, RHYTHM_NAME
from .sysex import Patch

HEADER = b"KoaBankFile00003PG-JV1080"
BANK_SIZE = 128
FILE_SIZE = len(HEADER) + BANK_SIZE * RECORD_SIZE

DEFAULT_FACTORY_DIRS = tuple(
    os.path.join(os.environ.get(env, ""), "VST3", "Roland", "JV-1080", "Patch")
    for env in ("CommonProgramFiles", "CommonProgramW6432") if os.environ.get(env)
)
FACTORY_BANK = "PR-A.bin"
TEMPLATE_INDEX = 0  # PR-A 001: a plain four-tone patch


class FactoryBankMissing(Exception):
    pass


def find_factory_dir(extra: str = "") -> str | None:
    for folder in ((extra,) if extra else ()) + DEFAULT_FACTORY_DIRS:
        if folder and os.path.isfile(os.path.join(folder, FACTORY_BANK)):
            return folder
    return None


def read_bank(path: str) -> list[bytes]:
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(HEADER) or len(data) != FILE_SIZE:
        raise ValueError("not a JV-1080 plug-in bank")
    return [data[len(HEADER) + i * RECORD_SIZE:len(HEADER) + (i + 1) * RECORD_SIZE] for i in range(BANK_SIZE)]


def load_template(folder: str | None) -> bytes:
    if not folder:
        raise FactoryBankMissing("the JV-1080 plug-in's factory banks were not found")
    record = read_bank(os.path.join(folder, FACTORY_BANK))[TEMPLATE_INDEX]
    if record[RHYTHM_NAME:RHYTHM_NAME + 12] != b"-" * 12:
        raise ValueError("unexpected factory bank content")
    return record


def write_bank(path: str, records: list[bytes]) -> None:
    if len(records) != BANK_SIZE or any(len(r) != RECORD_SIZE for r in records):
        raise ValueError("a bank holds 128 records")
    with open(path, "wb") as f:
        f.write(HEADER)
        for r in records:
            f.write(r)


def init_patch() -> Patch:
    """A plain JV-1080 patch for the empty slots of a bank: one sawtooth tone, no effect send."""
    common = bytearray(0x48)
    common[0:12] = b"INIT PATCH  "
    common[0x0D:0x19] = bytes((0, 15, 0, 15, 7, 1, 15, 7, 1, 15, 127, 0))   # flat EQ
    common[0x1A] = 127                                                          # EFX output level
    common[0x1E] = common[0x20] = 63
    common[0x21:0x27] = bytes((0, 0, 0, 0, 0, 0))
    common[0x27:0x2C] = bytes((3, 0, 64, 17, 0))
    common[0x2C:0x2E] = bytes((7, 8))                                          # tempo 120
    common[0x2E:0x30] = bytes((127, 64))
    common[0x31:0x33] = bytes((2, 2))
    common[0x41] = 3
    common[0x44:0x48] = bytes((0, 0, 0, 0))
    tones = []
    for t in range(4):
        tone = bytearray(0x81)
        tone[0x00] = 1 if t == 0 else 0
        tone[0x01], tone[0x02] = 0, 2                    # INT-B
        tone[0x03], tone[0x04] = 1, 9                    # wave 26: Synth Saw 1
        tone[0x0C], tone[0x0D], tone[0x0F] = 1, 127, 127
        tone[0x11] = tone[0x12] = tone[0x13] = 1
        tone[0x14] = 1
        for c in range(12):
            tone[0x16 + 2 * c] = 63                      # controller depths 0
        tone[0x2D:0x35] = bytes((0, 0, 64, 0, 0, 0, 0, 0))
        tone[0x35:0x3D] = bytes((0, 0, 64, 0, 0, 0, 0, 0))
        tone[0x3D], tone[0x3E] = 48, 50                  # coarse / fine 0
        tone[0x40] = 12                                  # pitch keyfollow +100
        tone[0x41], tone[0x42] = 12, 50
        tone[0x43] = tone[0x44] = tone[0x45] = 7
        tone[0x4A:0x4E] = bytes((63, 63, 63, 63))
        tone[0x4E] = tone[0x4F] = 63
        tone[0x51] = 127
        tone[0x52] = 5
        tone[0x54], tone[0x55], tone[0x57] = 50, 63, 50
        tone[0x58] = tone[0x59] = tone[0x5A] = 7
        tone[0x5F:0x63] = bytes((127, 127, 127, 127))
        tone[0x63] = tone[0x64] = 63
        tone[0x65] = 127
        tone[0x68] = 7
        tone[0x6A] = 50
        tone[0x6B] = tone[0x6C] = tone[0x6D] = 7
        tone[0x6E:0x72] = bytes((0, 0, 0, 0))
        tone[0x72:0x75] = bytes((127, 127, 127))
        tone[0x75] = tone[0x76] = 63
        tone[0x77] = 64
        tone[0x78] = 7
        tone[0x7A] = 64
        tone[0x7B] = tone[0x7C] = 63
        tone[0x7E] = 127
        tones.append(bytes(tone))
    return Patch(bytes(common), tones, "INIT")
