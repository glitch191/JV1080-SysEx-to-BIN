"""Window behaviour: dropping only scans; nothing is written until Convert is clicked.

Drives the real window (hidden) without a mouse; skipped when no display is available.
"""

import glob
import os
import shutil
import tempfile
import time
import unittest

from jv1080_sysex_to_bin import bank, engine

from test_conversion import fake_factory, jv_patch, syx_bytes

try:
    from tkinterdnd2 import TkinterDnD
    from jv1080_sysex_to_bin import gui

    _root = TkinterDnD.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # no display / Tk
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class ScanThenConvert(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="j2b_gui_")
        self.out = os.path.join(self.tmp, "out")
        self.syx = os.path.join(self.tmp, "Leads.syx")
        with open(self.syx, "wb") as f:
            f.write(syx_bytes({0: jv_patch("Saw Lead"), 1: jv_patch("Vintage", wave=(2, 4, 13)),
                               2: jv_patch("Flanged", efx=14)}))
        self._settings, self._defaults = gui.SETTINGS, bank.DEFAULT_FACTORY_DIRS
        gui.SETTINGS = os.path.join(self.tmp, "settings.json")  # keep the user's settings untouched
        bank.DEFAULT_FACTORY_DIRS = ()                           # and never use the real plug-in
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.app = gui.App(self.root, [])
        self.app.settings.update(destination=self.out, plugin=fake_factory(os.path.join(self.tmp, "plugin")))
        self.app._show_settings()

    def tearDown(self) -> None:
        self.app._quit()
        gui.SETTINGS, bank.DEFAULT_FACTORY_DIRS = self._settings, self._defaults
        engine.cleanup_temp()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pump(self, until, timeout: float = 60.0) -> None:
        end = time.monotonic() + timeout
        while not until():
            self.assertLess(time.monotonic(), end, "timed out")
            self.root.update()
            time.sleep(0.02)

    def outputs(self) -> list[str]:
        return glob.glob(os.path.join(self.out, "**", "*.bin"), recursive=True)

    def column(self, name: str) -> list[str]:
        return [self.app.tree.set(i, name) for i in self.app.tree.get_children()]

    def test_drop_scans_and_waits_for_convert(self) -> None:
        self.app.add([self.syx])
        self.pump(lambda: self.app.pending)
        self.assertEqual(self.column("state"), ["New"] * 3)
        self.assertEqual(self.column("effect"), ["STEREO-EQ", "STEREO-EQ", "STEREO-FLANGER"])
        self.assertIn("SR-JV80-04 Vintage Synth wave replaced", self.column("notes")[1])
        self.assertIn("Scanned: 3 patch(es) into 1 bank(s)", self.app.status.cget("text"))
        self.assertIn("1 approximate", self.app.status.cget("text"))
        time.sleep(0.3)
        self.root.update()
        self.assertEqual(self.outputs(), [])  # nothing written before confirmation

        self.app.convert_btn.invoke()
        self.pump(lambda: self.app.done == 1 and not self.app.runner.running)
        self.pump(lambda: self.app.cancel_btn.instate(["disabled"]))
        self.assertEqual([os.path.basename(p) for p in self.outputs()], ["Leads.bin"])
        self.assertEqual(self.column("state"), ["Converted (approximate)"] * 3)
        self.assertFalse(self.app.dest_btn.instate(["disabled"]))

        self.app.add([self.syx])  # a second scan announces the replacement
        self.pump(lambda: self.app.pending)
        self.assertEqual(self.column("state"), ["Replace"] * 3)

    def test_option_change_rescans(self) -> None:
        self.app.add([self.syx])
        self.pump(lambda: self.app.pending)
        self.app.substitute.set(False)
        self.app._substitute_changed()
        self.pump(lambda: self.app.pending and not self.app._collecting)
        self.assertIn("wave muted", self.column("notes")[1])

    def test_missing_plugin_blocks_convert(self) -> None:
        self.app.settings["plugin"] = ""
        self.app._show_settings()
        self.app.add([self.syx])
        self.pump(lambda: self.app.pending)
        self.assertTrue(self.app.convert_btn.instate(["disabled"]))
        self.assertIn("not found", self.app.plugin_label.cget("text"))

    def test_clear_forgets_the_scan(self) -> None:
        self.app.add([self.syx])
        self.pump(lambda: self.app.pending)
        self.app.clear_btn.invoke()
        self.assertEqual(self.app.pending, {})
        self.assertEqual(self.app.tree.get_children(), ())
        self.app._convert()  # nothing to do
        self.root.update()
        self.assertEqual(self.outputs(), [])


if __name__ == "__main__":
    unittest.main()
