# JV1080-SysEx-to-BIN

Windows desktop app that converts Roland JV-1080 patch dumps (`.syx`, `.mid`) into bank files
(`.bin`) for the Roland Cloud JV-1080 plug-in. Sister project of EBL-to-WAV (same owner): the
window, the scan-then-convert flow, archive unpacking, build and CI come from it. Inspired by
https://github.com/sagamusix/JDTools (BSD, JD-800 plug-in only; no code shared).

## Working with the owner

- The owner writes in French: answer in French. Everything inside the repository (code, comments,
  UI text, docs, file names) must be in English: no French anywhere in the tree.
- No em dashes in user-facing prose (README, release notes, forum posts). Use colons or commas.
- The owner is new to GitHub and publishes with GitHub Desktop (commit, push) and the github.com
  website (releases).
- Ask before destructive or outward-facing actions (deleting files, publishing).
- The owner tests banks in the plug-in by ear: BANK > LOAD.

## Layout

```
jv1080_sysex_to_bin/
  __init__.py   APP_NAME, __version__ (single source of the version number)
  __main__.py   entry point: window by default, --cli for headless use, --help, --version
  sysex.py      .syx / SMF reading, DT1 messages -> memory image -> JV patches
  waves.py      JV wave list -> XV-5080 wave numbers, expansion-board substitutes
  effects.py    EFX / chorus / reverb -> plug-in MFX / chorus / reverb
  patch.py      one JV patch -> one 23,255-byte record (layout documented at the top)
  bank.py       bank file read / write, template from the plug-in's factory banks, INIT patch
  archives.py   .zip / .7z unpacking (copied from EBL-to-WAV)
  engine.py     scan (files, folders, archives), output naming, manifest, runner
  gui.py        tkinter + tkinterdnd2 window (scan first, then Convert)
tests/          unittest suite; builds synthetic dumps (tests/test_conversion.py: jv_patch, syx_bytes)
docs/FORMAT.md  what was measured about the .bin format and the conversion
app.py          PyInstaller entry point
build.py        builds dist/JV1080-SysEx-to-BIN.exe and the release .zip
make_icon.py    regenerates icon.ico and docs/icon.png (needs Pillow)
.github/workflows/build.yml   CI: tests on every push; on a v* tag, builds and attaches the .zip
```

## Commands

```
py -m pip install -r requirements.txt          # tkinterdnd2, py7zr
py -m jv1080_sysex_to_bin                      # run the window from source
py -m jv1080_sysex_to_bin --cli PATH... [--out DIR] [--mute-expansion] [--plugin DIR]
py -m unittest discover -s tests -v            # 21 tests (4 drive the real window, hidden)
py -m pip install -r requirements-build.txt    # + pyinstaller, pillow
py build.py                                    # dist/JV1080-SysEx-to-BIN.exe + dist/*-windows-x64.zip
```

Settings (destination, expansion option, plug-in folder) live in
`%APPDATA%\JV1080-SysEx-to-BIN\settings.json`. `J2B_7ZIP=off` ignores an installed 7-Zip.

## Architecture

1. Scan (`engine.collect_jobs`, in a thread from the GUI): walks dropped files, folders and
   archives, parses each dump, converts every patch once on a blank template to list its warnings.
   One `Job` per output bank (128 patches; more patches give `<name> 1.bin`, `<name> 2.bin`).
2. The GUI lists the patches (bank New / Replace) and writes nothing until Convert. Changing the
   destination or the expansion option re-scans.
3. Convert: the template record is read from the installed plug-in (`PR-A.bin` record 1) and the
   `Runner` writes the banks (`<dst>.tmp`, then rename). No Roland data ships with the tool.
4. `finalize` updates the hidden manifest `.jv1080-sysex-to-bin`; for dropped folders and archives
   it also removes banks of an earlier run that are no longer produced. Loose files share the
   destination folder, so nothing is removed there.

## Format facts (see docs/FORMAT.md)

- The plug-in stores XV-5080 style patches; its MFX list is Fantom-G style (78 types).
- The active effect's parameters live twice: SysEx-style area and the per-type memory from 0x48C3
  (the plug-in plays the latter). Chorus / reverb memories at 22,979 / 23,099.
- Validation reference: Preset D converted from factory SysEx matches `PR-D.bin` except the
  category, octave tweaks and hand-tuned presets; the owner confirmed it sounds identical.
- EFX types without factory examples (5, 21, 25-31, 35-40) follow the pattern of measured
  siblings and are flagged approximate. Expansion-board substitutes exist for SR-JV80-04 only;
  the other boards' wave lists are in their scanned owner's manuals (static.roland.com,
  SR-JV80-NN_OM.pdf).

## Conventions

- Version: `jv1080_sysex_to_bin/__init__.py`, the CHANGELOG heading and the git tag (`vX.Y.Z`) must match.
- Never commit dumps, banks, ROMs or manuals (copyright); `.gitignore` excludes them.
- Keep personal data out of the repo: no user names, e-mail addresses or absolute user paths.
  `LICENSE` holds the owner's name on purpose.
- README screenshots: capture only the app window with `PrintWindow`, using synthetic demo dumps
  (built with `tests/test_conversion.py: jv_patch, syx_bytes`).
- Match the existing code style: type hints, short docstrings, comments only where the reason
  is not obvious.
