"""One JV-1080 patch -> one 23,255-byte record of the plug-in's bank file.

Record layout (offsets in the record; "XV" = the XV-5080 SysEx parameter at that offset in its
block, the plug-in stores XV-5080 style patches):

    0x0000  name (12 characters), then constant bytes
    0x0054  Patch Common, XV 00-4E (0x50 bytes, the last one is 0)
    0x00A4  MFX: type, 16 header bytes, 32 parameters (4 nibbles each, value + 32768)
    0x0135  chorus: type, level, output assign, output select, 20 parameters
    0x0189  reverb: type, level, output assign, 20 parameters
    0x01DC  TMT (tone mix table, 41 bytes)
    0x0205  tone 1, XV 00-88 (+ 17 constant bytes); tones 2-4 follow every 0x9A bytes
    0x046D  rhythm set data (unused by patches, kept from the template)
    0x48C3  per-type effect memory: for each of the 78 MFX types a 4-byte header (the control
            assigns, only on the active type) and its parameters; then chorus and reverb.

The plug-in plays the per-type memory of the active type, so the converted parameters are
written there as well as in the SysEx-style area. Everything not converted comes from a template
record (a factory patch of the installed plug-in).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import effects, waves
from .sysex import Patch

RECORD_SIZE = 23255
NAME, COMMON, MFX, CHORUS, REVERB, TMT, TONE, TONE_SIZE = 0x00, 0x54, 0xA4, 0x135, 0x189, 0x1DC, 0x205, 0x9A
MFX_PARAMS, CHORUS_PARAMS, REVERB_PARAMS = 0xB5, 0x139, 0x18C
RHYTHM_NAME = 0x46D

# Per-type effect memory: offset of the 4-byte header of MFX types 1-78.
MFX_SLOT_HEADERS = (
    18627, 18675, 18719, 18763, 18791, 18847, 18951, 18975, 19031, 19095, 19119, 19175, 19243, 19295,
    19331, 19363, 19463, 19499, 19535, 19631, 19735, 19783, 19851, 19903, 19959, 20027, 20071, 20123,
    20167, 20223, 20283, 20355, 20419, 20491, 20587, 20615, 20643, 20679, 20715, 20787, 20815, 20847,
    20879, 20943, 20991, 21055, 21131, 21207, 21299, 21407, 21519, 21583, 21663, 21707, 21755, 21815,
    21883, 21919, 21959, 21979, 22035, 22079, 22163, 22287, 22323, 22355, 22395, 22439, 22479, 22519,
    22563, 22603, 22643, 22687, 22727, 22783, 22843, 22903,
)
CHORUS_SLOT = 22979   # chorus type 1, 9 parameters
REVERB_SLOT = 23099   # reverb type 1 (JV-1080 reverb), 4 parameters


def nibbles(value: int) -> bytes:
    v = value + 32768
    return bytes(((v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15))


def write_params(rec: bytearray, offset: int, values: list[int]) -> None:
    for i, v in enumerate(values):
        rec[offset + 4 * i:offset + 4 * i + 4] = nibbles(v)


# --------------------------------------------------------------------------- value conversions

# Above +100 % the factory conversions follow a steeper curve: measured points (JV value, XV - 64).
_VEL_HIGH = ((100, 32), (107, 37), (109, 38), (110, 39), (113, 42), (115, 45), (117, 47), (118, 49),
             (121, 54), (125, 63))


def vel_sens(v: int) -> int:
    """JV velocity sensitivity 0-125 (-100..+150 %) -> -63..+63, stored +64."""
    if v <= 100:
        return 64 + max(-63, int((v - 50) * 0.64))
    v = min(v, 125)
    for (x0, y0), (x1, y1) in zip(_VEL_HIGH, _VEL_HIGH[1:]):
        if x0 <= v <= x1:
            return 64 + y0 + (y1 - y0) * (v - x0) // (x1 - x0)
    return 127


TIME_SENS = (-100, -70, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 70, 100)
KEYFOLLOW = (-100, -70, -50, -30, -10, 0, 10, 20, 30, 40, 50, 70, 100, 120, 150, 200)


def time_sens(v: int) -> int:
    """JV time velocity sensitivity 0-14 (-100..+100 %) -> -63..+63, stored +64."""
    return 64 + int(TIME_SENS[min(v, 14)] * 63 / 100)


def pct10(table: tuple, v: int) -> int:
    """JV keyfollow / bias level index -> XV value in 10 % steps around 64."""
    return 64 + table[min(v, len(table) - 1)] // 10


# LFO / tone delay synchronised to the clock: JV value -> XV note index (factory conversions).
_SYNC_NOTES = ((0, 0), (6, 3), (8, 4), (9, 5), (11, 6), (16, 7), (18, 8), (24, 9), (30, 10), (36, 11),
               (48, 12), (56, 13), (62, 14), (67, 15), (80, 16), (84, 17), (92, 18), (104, 19), (113, 20),
               (120, 21))


def sync_note(v: int) -> int:
    note = 0
    for threshold, n in _SYNC_NOTES:
        if v >= threshold:
            note = n
    return note


def two_nibbles(rec: bytearray, offset: int, value: int) -> None:
    rec[offset], rec[offset + 1] = (value >> 4) & 15, value & 15


LFO_WAVES = (1, 0, 2, 4, 8, 9, 5, 10)        # JV waveform -> XV waveform
DELAY_MODES = {0: 0, 1: 1, 2: 0, 3: 0, 4: 0, 5: 2, 6: 3}


# --------------------------------------------------------------------------- matrix control

def build_matrix(common: bytes, tones: list[bytes]) -> tuple[list[tuple[int, list]], list[list[int]]]:
    """JV per-tone controllers (3 controllers x 4 destinations per tone) -> up to 4 XV matrix
    controls (source + 4 destination / sens pairs) and the per-tone switches, allocated tone by
    tone like the factory conversions: equal entries are shared, a full control gets a twin."""
    sources = (1, effects.PATCH_SOURCES[min(common[0x3A], 15)], effects.PATCH_SOURCES[min(common[0x3B], 15)])
    matrix: list[tuple[int, list]] = []
    switches = [[0] * 16 for _ in range(4)]
    for t in range(4):  # switched-off tones too, as the factory conversions do
        for c in range(3):
            src = sources[c]
            if not src:
                continue
            for e in range(4):
                dest, depth = tones[t][0x15 + 8 * c + 2 * e], tones[t][0x16 + 8 * c + 2 * e]
                if dest == 0 or depth == 63 or dest > 18:
                    continue
                entry, slot, switch = (dest, depth + 1), None, 1
                mirror = (dest, 128 - (depth + 1))  # same destination, opposite depth: REVERSE
                for m, (msrc, entries) in enumerate(matrix):
                    if msrc == src and entry in entries:
                        slot = 4 * m + entries.index(entry)
                        break
                    if (msrc == src and mirror in entries and mirror != entry
                            and not switches[t][4 * m + entries.index(mirror)]):
                        slot, switch = 4 * m + entries.index(mirror), 2
                        break
                if slot is None:
                    for m, (msrc, entries) in enumerate(matrix):
                        if msrc == src and len(entries) < 4:
                            entries.append(entry)
                            slot = 4 * m + len(entries) - 1
                            break
                if slot is None and len(matrix) < 4:
                    matrix.append((src, [entry]))
                    slot = 4 * (len(matrix) - 1)
                if slot is not None:
                    switches[t][slot] = switch
    return matrix, switches


# --------------------------------------------------------------------------- conversion

@dataclass
class Converted:
    record: bytes
    warnings: list[str] = field(default_factory=list)
    approximate: bool = False


def convert(patch: Patch, template: bytes, substitute: bool = True) -> Converted:
    if len(template) != RECORD_SIZE:
        raise ValueError("bad template record")
    rec = bytearray(template)
    c, tones = patch.common, patch.tones
    warnings: list[str] = []
    approximate = False

    name = patch.common[:12]
    rec[NAME:NAME + 12] = name
    _common(rec, c)

    # Waves first: a tone whose wave cannot be played is switched off.
    active, wave_ids = [], []
    for t in range(4):
        tone = tones[t]
        on = bool(tone[0x00])
        xv = 0
        if on:
            result = waves.convert_wave(tone[0x01], tone[0x02], (tone[0x03] << 4) | tone[0x04], substitute)
            xv = result[0]
            if result[2]:
                warnings.append(f"tone {t + 1}: {result[2]}")
            approximate |= result[1]
            on = xv > 0
        active.append(on)
        wave_ids.append(xv)

    _tmt(rec, c, tones, active)
    for t in range(4):
        _tone(rec, TONE + TONE_SIZE * t, tones[t], wave_ids[t])

    matrix, switches = build_matrix(c, tones)
    for m in range(4):
        src, entries = matrix[m] if m < len(matrix) else (0, [])
        base = COMMON + 0x2B + 9 * m
        rec[base] = src
        for e in range(4):
            dest, sens = entries[e] if e < len(entries) else (0, 64)
            rec[base + 1 + 2 * e], rec[base + 2 + 2 * e] = dest, sens
    for t in range(4):
        o = TONE + TONE_SIZE * t + 0x17
        rec[o:o + 16] = bytes(switches[t])

    _effects(rec, c, warnings)
    if any(w.startswith("effect") for w in warnings):
        approximate = True
    return Converted(bytes(rec), warnings, approximate)


def _common(rec: bytearray, c: bytes) -> None:
    x = COMMON
    rec[x:x + 12] = c[:12]
    rec[x + 0x0C] = 0                    # category: none in JV-1080 data
    rec[x + 0x0D] = 0                    # four-tone patch
    rec[x + 0x0E] = c[0x2E]              # level
    rec[x + 0x0F] = c[0x2F]              # pan
    rec[x + 0x10] = c[0x43]              # voice priority
    rec[x + 0x11] = rec[x + 0x12] = 64   # coarse / fine tune (none on the JV)
    rec[x + 0x13] = 61 + min(c[0x41], 6)  # octave shift
    rec[x + 0x14] = c[0x42]              # stretch tune
    rec[x + 0x15] = c[0x30]              # analog feel
    rec[x + 0x16] = 0 if c[0x33] else 1  # JV key assign SOLO -> MONO
    rec[x + 0x17] = rec[x + 0x18] = c[0x34]  # legato (+ retrigger, as the factory patches)
    rec[x + 0x19:x + 0x1E] = c[0x35:0x3A]    # portamento switch, mode, type, start, time
    rec[x + 0x1E] = 0                    # clock source: patch
    rec[x + 0x1F], rec[x + 0x20] = c[0x2C], c[0x2D]  # tempo (two nibbles, same encoding)
    rec[x + 0x21] = 0
    rec[x + 0x22:x + 0x27] = bytes((64,) * 5)  # cutoff / resonance / attack / release / velocity offsets
    rec[x + 0x27] = 13                   # output assign: per tone
    rec[x + 0x28] = 0                    # TMT control
    rec[x + 0x29], rec[x + 0x2A] = c[0x31], c[0x32]  # bender range up / down
    rec[x + 0x4F] = 0


def _tmt(rec: bytearray, c: bytes, tones: list[bytes], active: list[bool]) -> None:
    rec[TMT:TMT + 4] = c[0x44:0x48]      # structure / booster 1&2 and 3&4
    rec[TMT + 4] = 1                     # velocity control on (ranges below decide)
    vel_on = bool(c[0x40])
    for t in range(4):
        tone, o = tones[t], TMT + 5 + 9 * t
        lo, hi = (tone[0x0C], tone[0x0D]) if vel_on else (1, 127)
        fade = tone[0x0B] if vel_on else 0
        rec[o:o + 9] = bytes((1 if active[t] else 0, tone[0x0E], tone[0x0F], 0, 0,
                              max(1, lo), max(1, hi), fade, fade))


def _tone(rec: bytearray, o: int, j: bytes, wave: int) -> None:
    rec[o + 0x00] = j[0x65]                      # level
    rec[o + 0x01] = j[0x3D] + 16                 # coarse -48..+48
    rec[o + 0x02] = j[0x3E] + 14                 # fine -50..+50
    rec[o + 0x03] = j[0x3F]                      # random pitch
    rec[o + 0x04] = j[0x77]                      # pan
    rec[o + 0x05] = pct10(TIME_SENS, j[0x78])    # pan keyfollow
    rec[o + 0x06] = j[0x79]                      # random pan
    rec[o + 0x07] = j[0x7A]                      # alternate pan
    rec[o + 0x08] = 1                            # envelope mode: sustain
    mode = j[0x09]
    rec[o + 0x09] = DELAY_MODES.get(mode, 0)
    delay = j[0x0A]
    if mode == 2:          # PLAY-MATE: no XV equivalent
        delay = 0
    elif mode in (3, 4):   # clock / tap sync: a note value
        delay = 128 + sync_note(delay)
    two_nibbles(rec, o + 0x0A, delay)
    to_efx = j[0x7D] == 1                        # JV output assign: MIX, EFX, OUTPUT 1, 2
    rec[o + 0x0C] = j[0x7E]                      # dry (output level)
    send_cho, send_rev = j[0x7F], j[0x80]
    rec[o + 0x0D], rec[o + 0x0E] = (send_cho, send_rev) if to_efx else (127, 127)
    rec[o + 0x0F], rec[o + 0x10] = (127, 127) if to_efx else (send_cho, send_rev)
    rec[o + 0x11] = 0 if to_efx else 1           # MFX / output A
    rec[o + 0x12] = j[0x13]                      # receive bender
    rec[o + 0x13] = 1                            # receive expression
    rec[o + 0x14] = j[0x12]                      # receive hold-1
    rec[o + 0x15] = 0 if j[0x14] == 1 else 1     # receive pan mode: JV CONTINUOUS -> 0
    rec[o + 0x16] = j[0x10]                      # redamper
    # 0x17-0x26: matrix control switches (set by the caller)
    rec[o + 0x27] = 0                            # wave group: internal
    rec[o + 0x28:o + 0x2C] = nibbles(1 - 32768)  # group ID 1
    rec[o + 0x2C:o + 0x30] = nibbles(wave - 32768)
    rec[o + 0x30:o + 0x34] = nibbles(0 - 32768)  # mono: no right wave
    rec[o + 0x34] = j[0x05]                      # wave gain
    rec[o + 0x35], rec[o + 0x36] = j[0x06], j[0x07]  # FXM switch / colour
    rec[o + 0x37] = j[0x08] + 1                  # FXM depth
    rec[o + 0x38] = 0                            # tempo sync
    rec[o + 0x39] = pct10(KEYFOLLOW, j[0x40])    # pitch keyfollow
    rec[o + 0x3A] = j[0x41] + 52                 # pitch env depth -12..+12
    rec[o + 0x3B] = vel_sens(j[0x42])
    rec[o + 0x3C] = time_sens(j[0x43])
    rec[o + 0x3D] = time_sens(j[0x44])
    rec[o + 0x3E] = pct10(TIME_SENS, j[0x45])
    rec[o + 0x3F:o + 0x43] = j[0x46:0x4A]        # pitch env times
    rec[o + 0x43] = 64                           # pitch env level 0
    rec[o + 0x44:o + 0x48] = bytes(v + 1 for v in j[0x4A:0x4E])
    rec[o + 0x48] = j[0x50]                      # filter type
    rec[o + 0x49] = j[0x51]                      # cutoff
    rec[o + 0x4A] = pct10(KEYFOLLOW, j[0x52])
    rec[o + 0x4B] = 0                            # cutoff velocity curve: fixed
    rec[o + 0x4C] = 64                           # cutoff velocity sens: none (JV uses the env)
    rec[o + 0x4D] = j[0x53]                      # resonance
    rec[o + 0x4E] = vel_sens(j[0x54])
    rec[o + 0x4F] = j[0x55] + 1                  # TVF env depth
    rec[o + 0x50] = j[0x56] + 1                  # TVF env velocity curve
    rec[o + 0x51] = vel_sens(j[0x57])
    rec[o + 0x52] = time_sens(j[0x58])
    rec[o + 0x53] = time_sens(j[0x59])
    rec[o + 0x54] = pct10(TIME_SENS, j[0x5A])
    rec[o + 0x55:o + 0x59] = j[0x5B:0x5F]        # TVF env times
    rec[o + 0x59] = 0                            # TVF env level 0
    rec[o + 0x5A:o + 0x5E] = j[0x5F:0x63]        # TVF env levels 1-4
    rec[o + 0x5E] = pct10(TIME_SENS, j[0x68])    # bias level
    rec[o + 0x5F] = j[0x67]                      # bias point
    rec[o + 0x60] = j[0x66]                      # bias direction
    rec[o + 0x61] = j[0x69] + 1                  # TVA velocity curve
    rec[o + 0x62] = vel_sens(j[0x6A])
    rec[o + 0x63] = time_sens(j[0x6B])
    rec[o + 0x64] = time_sens(j[0x6C])
    rec[o + 0x65] = pct10(TIME_SENS, j[0x6D])
    rec[o + 0x66:o + 0x6A] = j[0x6E:0x72]        # TVA env times
    rec[o + 0x6A:o + 0x6D] = j[0x72:0x75]        # TVA env levels
    for n, (x, v) in enumerate(((0x6D, 0x2D), (0x7B, 0x35))):  # LFO 1, LFO 2
        x, v = o + x, j[v:v + 8]  # JV: waveform, key trigger, rate, offset, delay, fade mode, fade time, sync
        rec[x] = LFO_WAVES[min(v[0], 7)]
        two_nibbles(rec, x + 1, 128 + sync_note(v[2]) if v[7] else v[2])
        rec[x + 3] = v[3]                        # level offset
        rec[x + 4] = 0                           # rate detune
        rec[x + 5] = v[4]                        # delay time
        rec[x + 6] = 64                          # delay keyfollow
        rec[x + 7] = v[5]                        # fade mode
        rec[x + 8] = v[6]                        # fade time
        rec[x + 9] = v[1]                        # key trigger
        depths = (j[0x4E], j[0x63], j[0x75], j[0x7B]) if n == 0 else (j[0x4F], j[0x64], j[0x76], j[0x7C])
        rec[x + 10:x + 14] = bytes(d + 1 for d in depths)  # pitch, TVF, TVA, pan depth


def _effects(rec: bytearray, c: bytes, warnings: list[str]) -> None:
    mfx = effects.convert_efx(c)
    if mfx.warning:
        warnings.append(mfx.warning)
    rec[MFX] = mfx.type
    rec[MFX + 1:MFX + 17] = bytes(mfx.header)
    params = mfx.params + [0] * (32 - len(mfx.params))
    write_params(rec, MFX_PARAMS, params)
    for h in MFX_SLOT_HEADERS:
        rec[h:h + 4] = b"\0\0\0\0"
    head = MFX_SLOT_HEADERS[mfx.type - 1]
    rec[head:head + 4] = bytes(mfx.header[12:16])
    write_params(rec, head + 4, mfx.params)

    ch_head, ch = effects.convert_chorus(c)
    rec[CHORUS:CHORUS + 4] = bytes(ch_head)
    write_params(rec, CHORUS_PARAMS, ch + [0] * (20 - len(ch)))
    write_params(rec, CHORUS_SLOT, ch)

    rv_head, rv = effects.convert_reverb(c)
    rec[REVERB:REVERB + 3] = bytes(rv_head)
    write_params(rec, REVERB_PARAMS, rv + [0] * (20 - len(rv)))
    write_params(rec, REVERB_SLOT, rv)
