"""JV-1080 effects (EFX, chorus, reverb) -> the plug-in's multi-effect (MFX), chorus and reverb.

The plug-in uses a Fantom-G style list of 78 MFX types; the JV-1080's 40 EFX types map onto it
(the three parallel JV types, CHORUS/DELAY, FLANGER/DELAY and CHORUS/FLANGER, become the serial
versions). Each JV EFX has 12 parameters; the MFX keeps up to 32, and every rate or delay time
becomes three values: (0 = Hz / ms, 1 = note), the value, the note.

How each type converts was measured on 160 factory patches present both as JV-1080 SysEx and in
the plug-in's factory banks (2080_PTC.MID = Preset D and others). Types that no factory patch uses
follow the same pattern as their measured siblings and are reported as approximate.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- value tables


def rate_hz20(n: int) -> int:
    """JV rate 0-125 (0.05-10 Hz) -> plug-in rate in 0.05 Hz steps (1-200)."""
    n = max(0, min(n, 125))
    if n <= 99:
        return n + 1                                  # 0.05-5.00 Hz, 0.05 steps
    if n <= 119:
        return 100 + 2 * (n - 99)                     # 5.1-7.0 Hz, 0.1 steps
    return 140 + 10 * (n - 119)                       # 7.5-10.0 Hz, 0.5 steps


def delay_ms(n: int) -> int:
    """JV delay time 0-126 (0.0-500 ms) -> milliseconds (the plug-in keeps whole ms)."""
    n = max(0, min(n, 126))
    if n <= 50:
        ms = n / 10                                   # 0.0-5.0, 0.1 steps
    elif n <= 60:
        ms = 5 + (n - 50) / 2                         # 5.5-10, 0.5 steps
    elif n <= 90:
        ms = 10 + (n - 60)                            # 11-40, 1 ms steps
    elif n <= 116:
        ms = 40 + 10 * (n - 90)                       # 50-300, 10 ms steps
    else:
        ms = 300 + 20 * (n - 116)                     # 320-500, 20 ms steps
    return int(ms + 0.5)


def tap_time(n: int) -> tuple[int, int, int]:
    """JV long delay time (200-1000 ms or a note, Triple / Quadruple tap and Time control delay)
    -> (mode, ms, note). Notes start at 116 (a 16th note)."""
    if n >= 116:
        return 1, 1000, min(n - 110, 21)
    return 0, (200 + 5 * n if n <= 100 else 700 + 20 * (n - 100)), 12


def _rate(n: int) -> list[int]:
    return [0, rate_hz20(n), 12]


def _delay(n: int) -> list[int]:
    return [0, delay_ms(n), 12]


# --------------------------------------------------------------------------- EFX types
# Each entry: JV EFX type (1-40) -> (MFX type, control assigns, measured?, params(j) -> list).
# ``j`` is the list of the 12 JV EFX parameters.

def _od_level(j: list[int]) -> int:
    # The plug-in's overdrive is louder: factory patches scale the level to about 55 %.
    return round(j[5] * 0.55)


EFX = {
    1: (1, (3, 0), True, lambda j: [j[0], j[1], j[4], j[6], j[5], j[7], j[9], j[8], j[2], j[3], j[10]]),
    2: (35, (1, 2), True, lambda j: [j[0], j[2], j[3], j[4], j[1], _od_level(j)]),
    3: (36, (1, 2), True, lambda j: [j[0], j[2], j[3], j[4], j[1], _od_level(j)]),
    4: (13, (1, 2), True, lambda j: [1, j[0], 0, rate_hz20(j[1]), 12, j[2], j[3], j[4], j[5], 15, 15, j[6]]),
    5: (2, (1, 0), False, lambda j: [*j[0:8], j[8], j[10]]),
    6: (7, (1, 2), True, lambda j: j[0:5]),
    7: (8, (3, 1), True, lambda j: [j[0], j[4], j[5], j[3], 0, *_rate(j[1]), j[2], 0, 15, 15, j[6]]),
    8: (21, (1, 2), True, lambda j: [j[4], rate_hz20(j[1]), rate_hz20(j[3]), j[6], j[8], rate_hz20(j[0]),
                                     rate_hz20(j[2]), j[5], j[7], j[9], j[10]]),
    9: (40, (0, 3), True, lambda j: [j[1], 127 - j[0], 3 * j[3], j[4], j[5], j[6]]),
    10: (41, (0, 3), True, lambda j: [j[1], j[0], j[2], 0, j[5], j[6], j[7]]),
    11: (26, (1, 2), True, lambda j: [j[0], *_rate(j[1]), *j[2:8]]),
    12: (27, (2, 3), True, lambda j: [j[0], *_rate(j[1]), j[2], *_rate(j[3]), *j[4:8]]),
    13: (28, (1, 2), True, lambda j: [j[0], *_rate(j[1]), *j[2:8]]),
    14: (23, (1, 2), True, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[5], *j[7:11]]),
    15: (24, (1, 2), True, lambda j: [j[0], j[1], j[2], *_rate(j[3]), *j[4:11]]),
    16: (25, (3, 2), True, lambda j: [0, 7, j[0], *_rate(j[1]), j[2], j[5], j[3],
                                      0, min(200, 2 * rate_hz20(j[4])), 12, *j[6:10]]),
    17: (43, (1, 2), True, lambda j: [*_delay(j[1]), *_delay(j[2]), j[3], j[4], j[0], *j[5:11]]),
    18: (46, (2, 3), True, lambda j: [*_delay(j[1]), *_delay(j[2]), j[0], j[3], j[4], *_rate(j[5]), *j[6:12]]),
    19: (47, (1, 2), True, lambda j: [*tap_time(j[0]), *tap_time(j[1]), *tap_time(j[2]), *j[3:12]]),
    20: (48, (1, 2), True, lambda j: [*tap_time(j[0]), *tap_time(j[1]), *tap_time(j[2]), *tap_time(j[3]),
                                      j[8], j[9], *j[4:8], 15, 15, j[10], j[11]]),
    21: (53, (1, 2), False, lambda j: [*tap_time(j[0]), j[2], j[1], j[3], j[5], j[6], j[7], j[8]]),
    22: (62, (1, 4), True, lambda j: [j[1], j[3], *_delay(j[5]), 49, j[7], 127,
                                      j[2], j[4], *_delay(j[6]), 49, j[8], 127, 15, 15, j[10], j[11]]),
    23: (61, (1, 2), True, lambda j: [j[1], j[2], *_delay(j[3]), j[4], *j[6:10]]),
    24: (64, (1, 2), True, lambda j: j[0:8]),
    25: (65, (1, 2), False, lambda j: j[0:7]),
    # Combinations: [A1, A2, B1, B2, B3, B4, balance, level] on the JV side.
    26: (66, (1, 2), False, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[6], j[7]]),
    27: (67, (1, 2), False, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[5], j[6], j[7]]),
    28: (68, (1, 2), False, lambda j: [j[0], j[1], *_delay(j[2]), j[3], j[4], j[6], j[7]]),
    29: (69, (1, 2), False, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[6], j[7]]),
    30: (70, (1, 2), False, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[5], j[6], j[7]]),
    31: (71, (1, 2), False, lambda j: [j[0], j[1], *_delay(j[2]), j[3], j[4], j[6], j[7]]),
    32: (72, (1, 4), True, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[6], j[7]]),
    33: (73, (1, 5), True, lambda j: [j[0], j[1], j[2], *_rate(j[3]), j[4], j[5], j[6], j[7]]),
    34: (74, (1, 4), True, lambda j: [j[0], j[1], *_delay(j[2]), j[3], j[4], j[6], j[7]]),
    # [effect 1: 4 values, balance 1, effect 2: 3-4 values, balance 2, level]
    35: (75, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[4], *_delay(j[5]), j[6], j[7], j[8], j[9]]),
    36: (76, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[3], j[4], *_delay(j[5]), j[6], j[7], j[8], j[9]]),
    37: (77, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[3], j[4], *_rate(j[5]), j[6], j[7], j[8], j[9]]),
    38: (75, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[4], *_delay(j[5]), j[6], j[7], j[8], j[9]]),
    39: (76, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[3], j[4], *_delay(j[5]), j[6], j[7], j[8], j[9]]),
    40: (77, (1, 2), False, lambda j: [j[0], *_rate(j[1]), j[2], j[3], j[4], *_rate(j[5]), j[6], j[7], j[8], j[9]]),
}

EFX_NAMES = (
    "STEREO-EQ", "OVERDRIVE", "DISTORTION", "PHASER", "SPECTRUM", "ENHANCER", "AUTO-WAH", "ROTARY",
    "COMPRESSOR", "LIMITER", "HEXA-CHORUS", "TREMOLO-CHORUS", "SPACE-D", "STEREO-CHORUS",
    "STEREO-FLANGER", "STEP-FLANGER", "STEREO-DELAY", "MODULATION-DELAY", "TRIPLE-TAP-DELAY",
    "QUADRUPLE-TAP-DELAY", "TIME-CONTROL-DELAY", "2VOICE-PITCH-SHIFTER", "FBK-PITCH-SHIFTER",
    "REVERB", "GATE-REVERB", "OVERDRIVE>CHORUS", "OVERDRIVE>FLANGER", "OVERDRIVE>DELAY",
    "DISTORTION>CHORUS", "DISTORTION>FLANGER", "DISTORTION>DELAY", "ENHANCER>CHORUS",
    "ENHANCER>FLANGER", "ENHANCER>DELAY", "CHORUS>DELAY", "FLANGER>DELAY", "CHORUS>FLANGER",
    "CHORUS/DELAY", "FLANGER/DELAY", "CHORUS/FLANGER",
)

# Number of parameters the plug-in stores for each MFX type (its per-type parameter memory).
MFX_SIZES = {
    1: 11, 2: 10, 3: 10, 4: 6, 5: 13, 6: 25, 7: 5, 8: 13, 9: 15, 10: 5, 11: 13, 12: 16, 13: 12, 14: 8,
    15: 7, 16: 24, 17: 8, 18: 8, 19: 23, 20: 25, 21: 11, 22: 16, 23: 12, 24: 13, 25: 16, 26: 10, 27: 12,
    28: 10, 29: 13, 30: 14, 31: 17, 32: 15, 33: 17, 34: 23, 35: 6, 36: 6, 37: 8, 38: 8, 39: 17, 40: 6,
    41: 7, 42: 7, 43: 15, 44: 11, 45: 15, 46: 18, 47: 18, 48: 22, 49: 26, 50: 27, 51: 15, 52: 19,
    53: 10, 54: 11, 55: 14, 56: 16, 57: 8, 58: 9, 59: 4, 60: 13, 61: 10, 62: 20, 63: 30, 64: 8, 65: 7,
    66: 9, 67: 10, 68: 9, 69: 9, 70: 10, 71: 9, 72: 9, 73: 10, 74: 9, 75: 13, 76: 14, 77: 14,
}

# JV control sources -> plug-in sources (CC number, 96 bender, 97 aftertouch, 102 velocity...).
# The JV system controllers 1 / 2 become aftertouch / CC02, as in the factory conversions.
EFX_SOURCES = (0, 97, 2, 1, 2, 4, 7, 10, 11, 96, 97)
PATCH_SOURCES = (0, 97, 2, 1, 2, 4, 7, 10, 11, 96, 97, 105, 106, 102, 103, 0)


class MfxResult:
    def __init__(self, mfx_type: int, header: list[int], params: list[int], approximate: bool, warning: str):
        self.type, self.header, self.params = mfx_type, header, params
        self.approximate, self.warning = approximate, warning


def convert_efx(common: bytes) -> MfxResult:
    """MFX type, 16-byte header (sends, control sources, assigns) and parameters."""
    efx = common[0x0C] + 1
    j = list(common[0x0D:0x19])
    mfx_type, assigns, measured, fn = EFX[efx]
    params = [max(-20000, min(20000, int(v))) for v in fn(j)]
    if len(params) != MFX_SIZES[mfx_type]:
        raise AssertionError(f"EFX {efx}: {len(params)} parameters, the plug-in expects {MFX_SIZES[mfx_type]}")
    src1, src2 = EFX_SOURCES[min(common[0x1D], 10)], EFX_SOURCES[min(common[0x1F], 10)]
    header = [common[0x1A], common[0x1B], common[0x1C], 0,
              src1, common[0x1E] + 1, src2, common[0x20] + 1, 0, 64, 0, 64, *assigns, 0, 0]
    warning = ""
    if efx in (38, 39, 40):
        warning = f"effect {EFX_NAMES[efx - 1]} made serial"
    elif not measured:
        warning = f"effect {EFX_NAMES[efx - 1]} approximated"
    return MfxResult(mfx_type, header, params, bool(warning), warning)


def convert_chorus(common: bytes) -> tuple[list[int], list[int]]:
    """(header: type, level, output assign, output select), 9 parameters."""
    level, rate, depth, pre_delay, feedback, output = common[0x21:0x27]
    return [1, level, 0, output], [0, 7, pre_delay, 0, rate_hz20(rate), 12, depth, 90, feedback]


def convert_reverb(common: bytes) -> tuple[list[int], list[int]]:
    """(header: type, level, output assign), 4 parameters: JV type, time, HF damp, feedback."""
    rev_type, level, time, hf_damp, feedback = common[0x27:0x2C]
    return [1, level, 0], [rev_type, time, hf_damp, feedback]
