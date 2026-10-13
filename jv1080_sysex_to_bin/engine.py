"""Dropped files -> plug-in banks (.bin).

Every .syx / .mid file holding JV-1080 patches becomes one bank of 128 patches named after the
file (``<stem>.bin``; ``<stem> 1.bin``, ``<stem> 2.bin``... past 128 patches); empty slots get an
INIT patch. Output layout:

    loose file                      <destination>/<stem>.bin
    file in a dropped folder F      <destination>/<F>/<sub-folders>/<stem>.bin
    file in an archive A            <destination>/<A>/<archive layout>/<stem>.bin

Scanning reads and converts everything (to list the patches and their warnings) but writes
nothing; ``Runner`` writes the banks once the user confirms.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import archives, bank, effects, patch, sysex
from .archives import ScanCancelled, cleanup_stale_temp, cleanup_temp  # noqa: F401 (re-exported)

# --------------------------------------------------------------------------- destination

def documents_dir() -> str:
    """The current user's Documents folder, as Windows reports it (follows OneDrive or other
    redirections); ~/Documents elsewhere or if the lookup fails."""
    try:
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("data", ctypes.c_ubyte * 16)]

        folder = GUID()
        folder.data[:] = list(uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}").bytes_le)  # FOLDERID_Documents
        path = wintypes.LPWSTR()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(path)) == 0:
            try:
                return path.value
            finally:
                ctypes.windll.ole32.CoTaskMemFree(path)
    except (AttributeError, OSError, ValueError):
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


DEFAULT_DESTINATION = os.path.join(documents_dir(), "JV-1080 Banks")
MANIFEST = ".jv1080-sysex-to-bin"  # per output folder: every bank this tool wrote there
SYSEX_EXTS = (".syx", ".mid", ".midi", ".smf")


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:100] or "Untitled"


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path.rstrip("\\/")))[0]


# --------------------------------------------------------------------------- jobs

@dataclass
class PatchRow:
    number: int          # slot in the bank, 1-128
    name: str
    source: str          # where it was in the dump: "User 001", "Card 012", "Temporary"...
    effect: str          # JV EFX type
    notes: str           # conversion warnings, "" when exact
    approximate: bool


@dataclass
class Job:
    src: str             # .syx / .mid file
    bank: str            # bank file name without .bin
    folder: str          # output folder relative to the destination ("" for loose files)
    dst: str             # output .bin
    root: str            # output folder holding the manifest
    cleanup: bool        # remove banks of an earlier run that this run no longer writes
    patches: list[sysex.Patch] = field(default_factory=list)
    rows: list[PatchRow] = field(default_factory=list)

    @property
    def approximate(self) -> int:
        return sum(r.approximate for r in self.rows)


def _no_progress(text: str, done: int | None = None, total: int | None = None) -> None:
    pass


def _archive_tree(folder: str, base: str, own: str) -> tuple[str, ...]:
    """Output sub-folders for a folder inside an unpacked archive: the archive's own layout,
    without a leading folder that repeats the archive name."""
    rel = os.path.relpath(folder, base)
    parts = [] if rel == "." else [safe_name(p) for p in rel.split(os.sep)]
    if parts and parts[0].lower() == own.lower():
        parts = parts[1:]
    return tuple(parts)


def _scan(path: str, depth: int, found: list, errors: list, progress, place: tuple | None) -> int:
    """Collect (file, top output folder or None, sub-folders, cleanup) under ``path``; returns the
    ignored-file count. ``place`` = (top folder, base folder, sub-folder prefix, own name) for
    files below a dropped folder or inside an archive."""
    ignored = 0
    low = path.lower()
    if os.path.isdir(path):
        name = safe_name(os.path.basename(path.rstrip("\\/")) or "Banks")
        inner = place or (name, path, (), name)
        progress(f"Looking through {name}")
        for folder, _, names in os.walk(path):
            for n in sorted(names):
                if n.lower().endswith(SYSEX_EXTS + archives.ARCHIVES):
                    ignored += _scan(os.path.join(folder, n), depth, found, errors, progress, inner)
    elif low.endswith(archives.ARCHIVES) and os.path.isfile(path):
        if depth >= 3:
            return 0
        try:
            out = archives.extract_archive(path, progress)
            name = safe_name(_stem(path))
            if place:  # archive inside an archive or a folder: under its place in the outer layout
                top, base, prefix, own = place
                inner = (top, out, prefix + _archive_tree(os.path.dirname(path), base, own) + (name,), name)
            else:
                inner = (name, out, (), name)
            ignored += _scan(out, depth + 1, found, errors, progress, inner)
        except ScanCancelled:
            raise
        except Exception as e:  # corrupt / encrypted / unsupported archive
            errors.append((path, f"unreadable archive ({e})"))
    elif low.endswith(SYSEX_EXTS) and os.path.isfile(path):
        if place:
            top, base, prefix, own = place
            found.append((path, top, prefix + _archive_tree(os.path.dirname(path), base, own)))
        else:
            found.append((path, None, ()))
    else:
        ignored += 1
    return ignored


def _natural(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def _unique(dst: str, seen: set[str]) -> str:
    stem, ext = os.path.splitext(dst)
    n, out = 2, dst
    while out.lower() in seen:
        out, n = f"{stem} ({n}){ext}", n + 1
    seen.add(out.lower())
    return out


def describe(p: sysex.Patch, number: int, substitute: bool) -> PatchRow:
    """List row for a patch: its conversion warnings (computed on a blank template)."""
    converted = patch.convert(p, bytes(patch.RECORD_SIZE), substitute)
    notes = "; ".join(dict.fromkeys(w.split(": ", 1)[-1] for w in converted.warnings))
    efx = effects.EFX_NAMES[min(p.common[0x0C], 39)]
    return PatchRow(number, p.name, p.source, efx, notes, converted.approximate)


def collect_jobs(paths: list[str], destination: str, substitute: bool = True,
                 progress=_no_progress) -> tuple[list[Job], list[tuple[str, str]], int]:
    """One job per output bank. Returns (jobs, [(file, error)], ignored file count); a file
    without any JV-1080 patch counts as ignored."""
    found: list = []
    errors: list = []
    ignored = sum(_scan(os.path.abspath(p), 0, found, errors, progress, None) for p in paths)
    found.sort(key=lambda f: ([_natural(p) for p in ((f[1] or ""),) + f[2]], _natural(os.path.basename(f[0]))))
    jobs: list[Job] = []
    seen: set[str] = set()
    done: set[str] = set()
    for i, (path, top, sub) in enumerate(found):
        key = os.path.normcase(path)
        if key in done:
            continue
        done.add(key)
        progress(f"Reading {i + 1} / {len(found)}: {os.path.basename(path)}", i, len(found))
        try:
            dump = sysex.read_file(path)
        except (OSError, ValueError) as e:
            errors.append((path, str(e)))
            continue
        if not dump.patches:
            ignored += 1
            continue
        root = os.path.join(destination, top) if top else destination
        folder = os.path.join(top, *sub) if top else ""
        banks = [dump.patches[k:k + bank.BANK_SIZE] for k in range(0, len(dump.patches), bank.BANK_SIZE)]
        for b, patches in enumerate(banks):
            name = safe_name(_stem(path)) + (f" {b + 1}" if len(banks) > 1 else "")
            dst = _unique(os.path.join(root, *sub, name + ".bin"), seen)
            rows = [describe(p, n + 1, substitute) for n, p in enumerate(patches)]
            jobs.append(Job(path, _stem(dst), folder, dst, root, bool(top), patches, rows))
    return jobs, errors, ignored


# --------------------------------------------------------------------------- writing

def bank_records(job: Job, template: bytes, substitute: bool) -> list[bytes]:
    records = [patch.convert(p, template, substitute).record for p in job.patches]
    if len(records) < bank.BANK_SIZE:
        init = patch.convert(bank.init_patch(), template, substitute).record
        records += [init] * (bank.BANK_SIZE - len(records))
    return records


def process_job(job: Job, template: bytes, substitute: bool) -> dict:
    res = {"dst": job.dst, "src": job.src, "size": 0, "status": "ok", "message": "Converted"}
    tmp = job.dst + ".tmp"
    try:
        records = bank_records(job, template, substitute)
        os.makedirs(os.path.dirname(job.dst), exist_ok=True)
        bank.write_bank(tmp, records)
        os.replace(tmp, job.dst)
        res["size"] = os.path.getsize(job.dst)
        if job.approximate:
            res["message"] = "Converted (approximate)"
    except Exception as e:  # one broken file must not stop the batch
        res.update(status="error", message=f"Error: {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass
    return res


# Banks this tool wrote in an output folder are listed in a hidden manifest: a later run may
# replace or remove them, anything else in the folder belongs to the user and is never touched.

def _read_manifest(root: str) -> set[str]:
    try:
        with open(os.path.join(root, MANIFEST), encoding="utf-8") as f:
            return {os.path.normpath(os.path.join(root, line.strip())) for line in f if line.strip()}
    except OSError:
        return set()


def _write_manifest(root: str, files: set[str]) -> None:
    path = os.path.join(root, MANIFEST)
    files = sorted(os.path.relpath(f, root) for f in files if os.path.isfile(f))
    try:
        if not files:
            if os.path.exists(path):
                os.remove(path)
            return
        if os.path.exists(path):
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x80)  # normal, so it can be rewritten
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(files) + "\n")
        ctypes.windll.kernel32.SetFileAttributesW(path, 0x2)  # hidden
    except (OSError, AttributeError):
        pass


def existing_outputs(root: str) -> set[str]:
    """Banks a previous run of this tool wrote under ``root``."""
    return {p for p in _read_manifest(root) if os.path.isfile(p)}


def remove_stale(root: str, keep: set[str], before: set[str]) -> int:
    """Delete banks written by an earlier run that this run did not rewrite, then empty folders.
    Files the user added are never touched."""
    removed = 0
    keep_l = {k.lower() for k in keep}
    for path in before:
        if path.lower() not in keep_l:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    for base, dirs, files in os.walk(root, topdown=False):
        if base != root and not dirs and not files:
            try:
                os.rmdir(base)
            except OSError:
                pass
    return removed


def finalize(root: str, before: set[str], results: list[dict], complete: bool, cleanup: bool) -> int:
    """After a run: for a dropped folder or archive (``cleanup``), remove banks of an earlier
    run that are no longer produced; always update the manifest."""
    attempted = {r["dst"] for r in results}
    removed = remove_stale(root, attempted, before) if complete and cleanup else 0
    written = {r["dst"] for r in results if r["status"] == "ok"}
    kept = (before & attempted if complete else before) if cleanup else before
    _write_manifest(root, written | kept)
    return removed


# --------------------------------------------------------------------------- runner

class Runner:
    """Thread pool; results arrive in ``events`` as ("result", dict), then ("done", None)
    or ("cancelled", None)."""

    def __init__(self, events) -> None:
        self.events = events
        self._pool: ThreadPoolExecutor | None = None
        self._pending = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._pool is not None

    def submit(self, jobs: list[Job], template: bytes, substitute: bool) -> None:
        if not jobs:
            return
        with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=max(1, min(os.cpu_count() or 1, 4, len(jobs))))
                self._stop.clear()
            self._pending += len(jobs)
            pool = self._pool
        for job in jobs:
            pool.submit(self._run, job, template, substitute)

    def _run(self, job: Job, template: bytes, substitute: bool) -> None:
        if self._stop.is_set():
            return
        res = process_job(job, template, substitute)
        self.events.put(("result", res))
        if self._stop.is_set():
            return
        with self._lock:
            self._pending -= 1
            finished = self._pending == 0 and self._pool is not None
            pool = self._pool if finished else None
            if finished:
                self._pool = None
        if pool is not None:
            pool.shutdown(wait=False)
            self.events.put(("done", None))

    def cancel(self) -> None:
        """Stop now: queued banks are skipped, the ones being written are finished."""
        with self._lock:
            pool, self._pool, self._pending = self._pool, None, 0
        if pool is None:
            return
        self._stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        self.events.put(("cancelled", None))


def run_blocking(paths: list[str], destination: str, substitute: bool = True, factory_dir: str = "",
                 on_result=None) -> list[dict]:
    """Headless conversion (CLI / tests), with the same replace + cleanup as the window."""
    import queue
    try:
        template = bank.load_template(bank.find_factory_dir(factory_dir))
        jobs, errors, _ = collect_jobs(paths, destination, substitute)
        for path, err in errors:
            if on_result:
                on_result({"dst": path, "src": path, "size": 0, "status": "error", "message": err})
        roots = {j.root: j.cleanup for j in jobs}
        before = {r: existing_outputs(r) for r in roots}
        events: queue.Queue = queue.Queue()
        Runner(events).submit(jobs, template, substitute)
        results = []
        while len(results) < len(jobs):
            kind, payload = events.get()
            if kind == "result":
                results.append(payload)
                if on_result:
                    on_result(payload)
        root_of = {j.dst: j.root for j in jobs}
        for root, cleanup in roots.items():
            finalize(root, before[root], [r for r in results if root_of[r["dst"]] == root], True, cleanup)
        return results
    finally:
        cleanup_temp()
