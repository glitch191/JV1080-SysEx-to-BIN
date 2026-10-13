"""Conversion tests on synthetic JV-1080 data (no Roland data in the repository).

``jv_patch`` builds a JV-1080 patch, ``syx_bytes`` its DT1 messages, ``fake_factory`` a folder
that stands in for the plug-in's factory banks. A last test uses the real factory banks when the
plug-in is installed.
"""

import os
import shutil
import struct
import tempfile
import unittest
import zipfile

from jv1080_sysex_to_bin import bank, effects, engine, patch, sysex, waves


def jv_patch(name: str = "Test Patch", efx: int = 0, wave: tuple = (0, 2, 25), **common_values) -> sysex.Patch:
    """The INIT patch with a name, an EFX type (0-based) and tone 1's wave (group, ID, number)."""
    p = bank.init_patch()
    common = bytearray(p.common)
    common[0:12] = name.ljust(12)[:12].encode("ascii")
    common[0x0C] = efx
    for offset, value in common_values.items():
        common[int(offset[1:], 16)] = value
    tone = bytearray(p.tones[0])
    tone[0x01], tone[0x02] = wave[0], wave[1]
    tone[0x03], tone[0x04] = wave[2] >> 4, wave[2] & 15
    return sysex.Patch(bytes(common), [bytes(tone)] + p.tones[1:])


def dt1(address: int, data: bytes, device: int = 0x10) -> bytes:
    addr = bytes(((address >> 21) & 0x7F, (address >> 14) & 0x7F, (address >> 7) & 0x7F, address & 0x7F))
    body = addr + data
    return bytes((0xF0, 0x41, device, 0x6A, 0x12)) + body + bytes(((-sum(body)) & 0x7F, 0xF7))


def syx_bytes(patches: dict[int, sysex.Patch], split_tones: bool = False) -> bytes:
    """User patches (index 0-127 -> patch) as a SysEx dump. ``split_tones`` sends each tone as
    128 + 1 bytes, the second message crossing a 7-bit address boundary."""
    out = b""
    for index, p in patches.items():
        base = (0x11 << 21) | (index << 14)
        out += dt1(base, p.common)
        for t, off in enumerate(sysex.TONE_OFFSETS):
            if split_tones:
                out += dt1(base + off, p.tones[t][:128]) + dt1(base + off + 128, p.tones[t][128:])
            else:
                out += dt1(base + off, p.tones[t])
    return out


def smf_bytes(sysex_data: bytes) -> bytes:
    """A format-0 MIDI file holding the messages, each one split into F0 + F7 packets."""
    events = b""
    for m in sysex.sysex_messages(sysex_data):
        half = len(m) // 2
        first, second = m[1:half], m[half:]
        events += b"\x00\xF0" + _vlq(len(first)) + first + b"\x00\xF7" + _vlq(len(second)) + second
    events += b"\x00\xFF\x2F\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(events)) + events


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    while n > 0x7F:
        n >>= 7
        out.insert(0, 0x80 | (n & 0x7F))
    return bytes(out)


def blank_template() -> bytes:
    rec = bytearray(patch.RECORD_SIZE)
    rec[patch.RHYTHM_NAME:patch.RHYTHM_NAME + 12] = b"-" * 12
    return bytes(rec)


def fake_factory(folder: str) -> str:
    """A folder with a PR-A.bin made of blank records, like the plug-in's Patch folder."""
    os.makedirs(folder, exist_ok=True)
    bank.write_bank(os.path.join(folder, bank.FACTORY_BANK), [blank_template()] * bank.BANK_SIZE)
    return folder


class SysexReading(unittest.TestCase):
    def test_user_patches_in_address_order(self) -> None:
        data = syx_bytes({127: jv_patch("Last"), 0: jv_patch("First"), 5: jv_patch("Sixth")})
        dump = sysex.parse(data)
        self.assertEqual([p.name for p in dump.patches], ["First", "Sixth", "Last"])
        self.assertEqual([p.source for p in dump.patches], ["User 001", "User 006", "User 128"])
        self.assertEqual(dump.checksum_errors, 0)

    def test_split_messages_and_address_carry(self) -> None:
        p = jv_patch("Split")
        dump = sysex.parse(syx_bytes({3: p}, split_tones=True))
        self.assertEqual(dump.patches[0].tones, p.tones)

    def test_midi_file(self) -> None:
        dump = sysex.parse(smf_bytes(syx_bytes({0: jv_patch("A"), 1: jv_patch("B")})))
        self.assertEqual([p.name for p in dump.patches], ["A", "B"])

    def test_incomplete_patch_is_skipped(self) -> None:
        data = syx_bytes({0: jv_patch("Complete")}) + dt1((0x11 << 21) | (1 << 14), jv_patch("Half").common)
        self.assertEqual([p.name for p in sysex.parse(data).patches], ["Complete"])

    def test_bad_checksum_is_counted(self) -> None:
        data = bytearray(syx_bytes({0: jv_patch()}))
        data[-2] ^= 1
        self.assertEqual(sysex.parse(bytes(data)).checksum_errors, 1)


class PatchConversion(unittest.TestCase):
    def setUp(self) -> None:
        self.template = blank_template()

    def test_layout(self) -> None:
        rec = patch.convert(jv_patch("My Lead", _2E=100), self.template).record
        self.assertEqual(len(rec), patch.RECORD_SIZE)
        self.assertEqual(rec[0:12], b"My Lead     ")
        self.assertEqual(rec[patch.COMMON:patch.COMMON + 12], b"My Lead     ")
        self.assertEqual(rec[patch.COMMON + 0x0E], 100)  # level
        tone = patch.TONE
        self.assertEqual(rec[tone + 0x01], 64)            # coarse 0
        self.assertEqual(rec[tone + 0x39], 74)            # pitch keyfollow +100 %
        self.assertEqual(patch.nibbles(529 - 32768), rec[tone + 0x2C:tone + 0x30])  # INT-B 26 = XV 529

    def test_internal_waves(self) -> None:
        self.assertEqual(waves.convert_wave(0, 1, 0, True)[0], 19)     # Ac Piano1 A
        self.assertEqual(waves.convert_wave(0, 2, 192, True)[0], 887)  # DC
        self.assertEqual(len(set(waves.INT_A_XV + waves.INT_B_XV)), 448)

    def test_expansion_wave_substituted_or_muted(self) -> None:
        p = jv_patch(wave=(2, 4, 0))  # SR-JV80-04 wave 1: JP-8 Saw A
        on = patch.convert(p, self.template, substitute=True)
        self.assertTrue(on.approximate)
        self.assertEqual(on.record[patch.TONE + 0x2C:patch.TONE + 0x30], patch.nibbles(535 - 32768))
        self.assertEqual(on.record[patch.TMT + 5], 1)
        off = patch.convert(p, self.template, substitute=False)
        self.assertEqual(off.record[patch.TMT + 5], 0)  # tone switched off
        self.assertIn("muted", off.warnings[0])

    def test_every_expansion_board_has_substitutes(self) -> None:
        self.assertEqual(sorted(waves.EXPANSION_SUBSTITUTES), list(range(1, 20)))
        for board, subs in waves.EXPANSION_SUBSTITUTES.items():
            self.assertEqual(len(subs), len(waves.EXPANSION_WAVE_NAMES[board]), board)
            self.assertTrue(all(1 <= v <= 1083 for v in subs), board)
            last = waves.convert_wave(waves.GROUP_EXP, board, len(subs) - 1, True)
            self.assertEqual(last[:2], (subs[-1], True))
            self.assertIn(waves.EXPANSION_NAMES[board], last[2])

    def test_every_efx_type(self) -> None:
        for efx in range(40):
            c = patch.convert(jv_patch(efx=efx), self.template)
            mfx_type = c.record[patch.MFX]
            self.assertEqual(mfx_type, effects.EFX[efx + 1][0])
            head = patch.MFX_SLOT_HEADERS[mfx_type - 1]
            self.assertEqual(c.record[head:head + 4], bytes(effects.EFX[efx + 1][1]) + b"\0\0")

    def test_rate_and_delay_tables(self) -> None:
        self.assertEqual(effects.rate_hz20(40), 41)
        self.assertEqual(effects.rate_hz20(124), 190)
        self.assertEqual([effects.delay_ms(n) for n in (10, 55, 64, 103, 111, 122, 126)],
                         [1, 8, 14, 170, 250, 420, 500])
        self.assertEqual(effects.tap_time(52), (0, 460, 12))
        self.assertEqual(effects.tap_time(122), (1, 1000, 12))

    def test_matrix_controls(self) -> None:
        p = jv_patch()
        tones = [bytearray(t) for t in p.tones]
        tones[0][0x15:0x17] = bytes((2, 73))   # controller 1 -> cutoff +10
        tones[1][0x15:0x17] = bytes((2, 53))   # same destination, opposite depth
        tones[1][0x00] = 1
        matrix, switches = patch.build_matrix(p.common, [bytes(t) for t in tones])
        self.assertEqual(matrix, [(1, [(2, 74)])])
        self.assertEqual((switches[0][0], switches[1][0]), (1, 2))  # ON, REVERSE


class Banks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="j2b_test_")
        self.out = os.path.join(self.tmp, "out")
        self.factory = fake_factory(os.path.join(self.tmp, "plugin"))

    def tearDown(self) -> None:
        engine.cleanup_temp()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name: str, data: bytes) -> str:
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_one_bank_per_file_with_init_fill(self) -> None:
        src = self.write("My Bank.syx", syx_bytes({0: jv_patch("One"), 1: jv_patch("Two")}))
        results = engine.run_blocking([src], self.out, factory_dir=self.factory)
        self.assertEqual([r["status"] for r in results], ["ok"])
        records = bank.read_bank(os.path.join(self.out, "My Bank.bin"))
        self.assertEqual([r[:12] for r in records[:3]], [b"One         ", b"Two         ", b"INIT PATCH  "])
        self.assertEqual(os.path.getsize(os.path.join(self.out, "My Bank.bin")), bank.FILE_SIZE)

    def test_more_than_128_patches(self) -> None:
        data = syx_bytes({i: jv_patch(f"U{i}") for i in range(128)})
        card = b""
        for i in range(10):
            p, base = jv_patch(f"C{i}"), (0x21 << 21) | (i << 14)
            card += dt1(base, p.common) + b"".join(dt1(base + o, t) for o, t in zip(sysex.TONE_OFFSETS, p.tones))
        src = self.write("Big.syx", data + card)
        engine.run_blocking([src], self.out, factory_dir=self.factory)
        self.assertEqual(sorted(os.listdir(self.out)), [".jv1080-sysex-to-bin", "Big 1.bin", "Big 2.bin"])

    def test_archive_and_folder_layout(self) -> None:
        dump = syx_bytes({0: jv_patch("Zipped")})
        archive = os.path.join(self.tmp, "Collection.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("Collection/Leads/Leads.syx", dump)
            z.writestr("readme.txt", "not looked at")
            z.writestr("Yamaha.syx", bytes((0xF0, 0x43, 0x00, 0x00, 0xF7)))  # SysEx, but no JV-1080 patch
        folder = os.path.join(self.tmp, "Dumps")
        self.write(os.path.join("Dumps", "Pads", "Pads.mid"), smf_bytes(dump))
        jobs, errors, ignored = engine.collect_jobs([archive, folder], self.out)
        self.assertEqual(errors, [])
        self.assertEqual(ignored, 1)
        self.assertEqual(sorted(os.path.relpath(j.dst, self.out) for j in jobs),
                         [os.path.join("Collection", "Leads", "Leads.bin"), os.path.join("Dumps", "Pads", "Pads.bin")])

    def test_rerun_replaces_and_cleans_up(self) -> None:
        folder = os.path.join(self.tmp, "Set")
        first = self.write(os.path.join("Set", "A.syx"), syx_bytes({0: jv_patch("A")}))
        engine.run_blocking([folder], self.out, factory_dir=self.factory)
        mine = os.path.join(self.out, "Set", "mine.txt")
        self.write(os.path.relpath(mine, self.tmp), b"user file")
        os.rename(first, os.path.join(folder, "B.syx"))
        engine.run_blocking([folder], self.out, factory_dir=self.factory)
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "Set"))), [".jv1080-sysex-to-bin", "B.bin", "mine.txt"])

    def test_missing_plugin(self) -> None:
        src = self.write("X.syx", syx_bytes({0: jv_patch()}))
        defaults, bank.DEFAULT_FACTORY_DIRS = bank.DEFAULT_FACTORY_DIRS, ()
        try:
            with self.assertRaises(bank.FactoryBankMissing):
                engine.run_blocking([src], self.out, factory_dir=os.path.join(self.tmp, "nowhere"))
        finally:
            bank.DEFAULT_FACTORY_DIRS = defaults
        self.assertFalse(os.path.exists(os.path.join(self.out, "X.bin")))


@unittest.skipUnless(bank.find_factory_dir(), "the JV-1080 plug-in is not installed")
class RealPlugin(unittest.TestCase):
    def test_template_and_bank(self) -> None:
        template = bank.load_template(bank.find_factory_dir())
        rec = patch.convert(jv_patch("Real"), template).record
        tmp = tempfile.mkdtemp(prefix="j2b_real_")
        try:
            path = os.path.join(tmp, "Real.bin")
            bank.write_bank(path, [rec] * bank.BANK_SIZE)
            self.assertEqual(bank.read_bank(path)[0], rec)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
