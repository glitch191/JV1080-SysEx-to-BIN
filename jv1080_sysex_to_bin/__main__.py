"""Entry point: GUI by default (paths given on the command line - e.g. files dropped on the .exe
icon - are scanned right away); ``--cli PATH... [--out DIR] [--mute-expansion] [--plugin DIR]``
runs headless."""

from __future__ import annotations

import os
import sys

USAGE = r"""Usage:
  JV1080-SysEx-to-BIN [PATH...]          open the window (PATHs are scanned right away)
  JV1080-SysEx-to-BIN --cli PATH... [--out DIR] [--mute-expansion] [--plugin DIR]

PATH: .syx / .mid files with JV-1080 patches, folders containing them, or .zip / .7z archives.
DIR (--out): output folder (default: Documents\JV-1080 Banks).
--mute-expansion: silence tones that use SR-JV80 expansion waves instead of replacing them with
                  the closest internal wave.
--plugin DIR: folder holding the plug-in's factory banks (PR-A.bin...), if not found by itself."""


def _cli(argv: list[str]) -> int:
    from . import bank, engine

    destination, substitute, plugin = engine.DEFAULT_DESTINATION, True, ""
    paths = []
    it = iter(argv)
    for a in it:
        if a == "--out":
            destination = next(it, destination)
        elif a == "--plugin":
            plugin = next(it, plugin)
        elif a == "--mute-expansion":
            substitute = False
        elif not a.startswith("--"):
            paths.append(a)
    out = sys.stdout or open(os.devnull, "w", encoding="utf-8")  # the .exe has no console
    if not paths:
        print(USAGE, file=out)
        return 2
    try:
        results = engine.run_blocking(paths, destination, substitute, plugin,
                                      lambda r: print(f"[{r['status']}] {r['dst']} {r['message']}",
                                                      file=out, flush=True))
    except bank.FactoryBankMissing as e:
        print(f"[error] {e}: use --plugin DIR", file=out)
        return 1
    return 1 if not results or any(r["status"] == "error" for r in results) else 0


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "--version"):
        from . import APP_NAME, __version__
        out = sys.stdout or open(os.devnull, "w", encoding="utf-8")
        print(f"{APP_NAME} {__version__}" if argv[0] == "--version" else USAGE, file=out)
        return
    if "--cli" in argv:
        sys.exit(_cli([a for a in argv if a != "--cli"]))
    from .gui import main as gui_main
    gui_main(argv)


if __name__ == "__main__":
    main()
