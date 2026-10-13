"""Unpack .zip / .7z archives into temporary folders (shared with EBL-to-WAV, same owner).

Zip members are decompressed in parallel; a solid .7z goes through 7-Zip's own 7z.exe when it is
installed (much faster), otherwise through py7zr. ``progress(text, done, total)`` reports the
uncompressed bytes written; raising ScanCancelled from it stops the extraction.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

ARCHIVES = (".zip", ".7z")
_temp_dirs: list[str] = []


# Scan progress: ``progress(text, done, total)`` is called from the scanning thread; ``done`` and
# ``total`` are byte counts while unpacking an archive, ``None`` when the step has no measure.

def _no_progress(text: str, done: int | None = None, total: int | None = None) -> None:
    pass


def _safe_member_path(out: str, name: str) -> str | None:
    """Where an archive member goes under ``out``: no absolute paths, no "..", no characters
    Windows forbids. None if it would still end up outside ``out``."""
    parts = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", p).rstrip(" .") for p in re.split(r"[\\/]+", name)]
    parts = [p for p in parts if p and p not in (".", "..")]
    if not parts:
        return None
    target = os.path.abspath(os.path.join(out, *parts))
    return target if os.path.commonpath([target, os.path.abspath(out)]) == os.path.abspath(out) else None


class _ByteProgress:
    """Thread-safe byte counter shared by the extraction threads. ``add`` reports progress and
    raises ScanCancelled for every thread once one of them was told to stop."""

    def __init__(self, label: str, total: int, progress) -> None:
        self.label, self.total, self.progress = label, total, progress
        self.done = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()
        progress(label, 0, total)

    def add(self, n: int) -> None:
        if self.stop.is_set():
            raise ScanCancelled()
        with self.lock:
            self.done += n
            done = min(self.done, self.total)
        try:
            self.progress(self.label, done, self.total)
        except ScanCancelled:
            self.stop.set()
            raise


def _parallel(tasks: list, progress: _ByteProgress) -> None:
    """Run ``tasks`` (callables) on one thread per logical CPU; the first failure stops the others
    and is raised (a cancellation wins over other errors)."""
    workers = max(1, min(os.cpu_count() or 1, len(tasks)))
    if workers == 1:
        for task in tasks:
            task()
        return
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(task) for task in tasks]:
            try:
                future.result()
            except BaseException as e:
                progress.stop.set()
                errors.append(e)
    if errors:
        raise next((e for e in errors if isinstance(e, ScanCancelled)), errors[0])


def _extract_zip(path: str, out: str, label: str, progress) -> None:
    """Members are decompressed in parallel (zlib releases the GIL), each thread with its own
    handle on the archive."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
    files = []
    for m in members:
        target = _safe_member_path(out, m.filename)
        if target is None:
            continue
        if m.is_dir():
            os.makedirs(target, exist_ok=True)
        else:
            files.append((m, target))
    files.sort(key=lambda f: -f[0].file_size)  # big members first: better load balance
    counter = _ByteProgress(label, sum(m.file_size for m, _ in files), progress)
    local = threading.local()
    handles: list = []
    handles_lock = threading.Lock()

    def extract(member, target) -> None:
        z = getattr(local, "zip", None)
        if z is None:
            z = local.zip = zipfile.ZipFile(path)
            with handles_lock:
                handles.append(z)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(member) as src, open(target, "wb") as dst:
            while chunk := src.read(2**20):
                dst.write(chunk)
                counter.add(len(chunk))

    try:
        _parallel([lambda m=m, t=t: extract(m, t) for m, t in files], counter)
    finally:
        for z in handles:
            z.close()


# --- .7z: one big block / solid archive -> 7-Zip's own decoder if installed (several times
# faster); one block per file -> py7zr (faster there); no 7-Zip, or 7-Zip fails -> py7zr.

_7zip_path: list = []  # cache: [path or None]


def find_7zip() -> str | None:
    """7-Zip's 7z.exe if it is installed (set J2B_7ZIP=off to ignore it)."""
    if os.environ.get("J2B_7ZIP", "").lower() == "off":
        return None
    if _7zip_path:
        return _7zip_path[0]
    candidates = []
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\7-Zip", 0, winreg.KEY_READ | view) as key:
                        for value in ("Path64", "Path"):
                            try:
                                candidates.append(os.path.join(winreg.QueryValueEx(key, value)[0], "7z.exe"))
                            except OSError:
                                pass
                except OSError:
                    pass
    except ImportError:
        pass
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(env):
            candidates.append(os.path.join(os.environ[env], "7-Zip", "7z.exe"))
    candidates.append(shutil.which("7z") or "")
    found = next((c for c in candidates if c and os.path.isfile(c)), None)
    _7zip_path.append(found)
    return found


def _extract_7z_native(exe: str, path: str, out: str, counter: _ByteProgress) -> None:
    """Run 7z.exe (hidden window); its percentage output drives the progress; a cancellation
    kills it. 7-Zip itself drops absolute paths and ".." from member names."""
    import subprocess
    cmd = [exe, "x", path, f"-o{out}", "-y", "-p", "-mmt=on", "-bso0", "-bsp1", "-bb0"]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    errors: list[bytes] = []
    reader = threading.Thread(target=lambda: errors.append(proc.stderr.read()), daemon=True)
    reader.start()
    reported = 0
    try:
        while chunk := proc.stdout.read1(256):
            percents = re.findall(rb"(\d{1,3})%", chunk)
            if percents:
                now = counter.total * min(100, int(percents[-1])) // 100
                if now > reported:
                    counter.add(now - reported)
                    reported = now
    except ScanCancelled:
        proc.kill()
        proc.wait()
        raise
    code = proc.wait()
    reader.join(timeout=5)
    if code >= 2:  # 0 = OK, 1 = warnings, 2+ = errors
        message = b"".join(errors).decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"7-Zip exit code {code}: {message[-1] if message else ''}")
    if counter.total > reported:
        counter.add(counter.total - reported)


def _extract_7z_py(path: str, out: str, counter: _ByteProgress) -> None:
    """py7zr through our own file writers, called from the extracting thread while data is
    decompressed: progress follows the data and a ScanCancelled stops the extraction at once."""
    import py7zr
    import py7zr.io

    writers: list = []
    writers_lock = threading.Lock()

    class Writer(py7zr.io.Py7zIO):
        def __init__(self, target: str | None) -> None:
            self.file = None
            if target:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                self.file = open(target, "wb")
            self.length = 0

        def write(self, data) -> int:
            counter.add(len(data))
            self.length += len(data)
            return self.file.write(data) if self.file else len(data)

        def read(self, size=None) -> bytes: return b""
        def seek(self, offset, whence=0) -> int: return 0
        def size(self) -> int: return self.length

        def flush(self) -> None:
            if self.file:
                self.file.flush()

        def close(self) -> None:
            if self.file:
                self.file.close()
                self.file = None

    class Factory(py7zr.io.WriterFactory):
        def create(self, filename: str) -> "Writer":
            # py7zr passes the full output path (out + member name): keep the member part.
            full, root = os.path.abspath(filename), os.path.abspath(out)
            if os.path.isabs(filename) and os.path.commonpath([full, root]) == root:
                filename = os.path.relpath(full, root)
            writer = Writer(_safe_member_path(out, filename))
            with writers_lock:
                writers.append(writer)
            return writer

    try:
        with py7zr.SevenZipFile(path, "r") as z:
            z.extractall(out, factory=Factory())
    finally:
        for writer in writers:
            writer.close()


def _extract_7z(path: str, out: str, label: str, progress) -> None:
    import py7zr
    with py7zr.SevenZipFile(path, "r") as z:
        info = z.archiveinfo()
        entries = [e for e in z.list() if not e.is_directory]
    counter = _ByteProgress(label, sum(e.uncompressed or 0 for e in entries), progress)
    blocks = info.blocks or 1
    if len(entries) > 1 and blocks >= len(entries):  # non-solid: every file is its own block
        _extract_7z_py(path, out, counter)
        return
    exe = find_7zip()
    if exe:
        try:
            _extract_7z_native(exe, path, out, counter)
            return
        except ScanCancelled:
            raise
        except Exception:  # 7-Zip missing a codec, damaged install...: start again with py7zr
            shutil.rmtree(out, ignore_errors=True)
            os.makedirs(out, exist_ok=True)
            counter = _ByteProgress(label, counter.total, progress)
    _extract_7z_py(path, out, counter)


def extract_archive(path: str, progress=_no_progress) -> str:
    """Unpack a .zip / .7z into a temporary folder (removed by ``cleanup_temp``), reporting the
    uncompressed bytes written so far."""
    out = tempfile.mkdtemp(prefix=TEMP_PREFIX)
    _temp_dirs.append(out)
    label = f"Unpacking {os.path.basename(path)}"
    if path.lower().endswith(".7z"):
        _extract_7z(path, out, label, progress)
    else:
        _extract_zip(path, out, label, progress)
    return out


TEMP_PREFIX = "jv1080-sysex-to-bin_"


class ScanCancelled(Exception):
    """Raised by a progress callback to stop a scan (e.g. the window is closing)."""


def cleanup_temp() -> None:
    while _temp_dirs:
        shutil.rmtree(_temp_dirs.pop(), ignore_errors=True)


def cleanup_stale_temp(max_age_hours: float = 6.0) -> None:
    """Remove unpacked archives left behind by an earlier session that could not clean up
    (killed, crashed). Recent folders are kept: another open window may still be using them."""
    import time
    limit = time.time() - max_age_hours * 3600
    base = tempfile.gettempdir()
    try:
        names = os.listdir(base)
    except OSError:
        return
    for name in names:
        path = os.path.join(base, name)
        try:
            if name.startswith(TEMP_PREFIX) and os.path.isdir(path) and os.path.getmtime(path) < limit:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

