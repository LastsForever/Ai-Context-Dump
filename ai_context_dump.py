#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import fnmatch
import shutil
from dataclasses import dataclass
from itertools import chain
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Optional, TextIO


SETTINGS_FILE_DEFAULT = "ai-context-dump.settings.json"


@dataclass(frozen=True)
class OutputConfig:
    mode: str  # structure | code | both | split
    single_file: str
    structure_file: str
    code_file: str


@dataclass(frozen=True)
class ClipboardConfig:
    enabled: bool
    text: str


@dataclass(frozen=True)
class IgnoreConfig:
    extensions: frozenset[str]          # e.g. {".dll", ".png"}
    patterns: tuple[str, ...]           # optional, glob-style


@dataclass(frozen=True)
class Settings:
    root: Path
    os_style: str                       # auto | posix | windows
    output: OutputConfig
    clipboard: ClipboardConfig
    ignore: IgnoreConfig


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_ext(ext: str) -> str:
    e = (ext or "").strip()
    return e if e.startswith(".") else f".{e}" if e else ""


def _pick_os_style(value: str) -> str:
    v = (value or "auto").strip().lower()
    return v if v in {"auto", "posix", "windows"} else "auto"


def load_settings(settings_path: Path) -> Settings:
    raw = _load_json(settings_path)

    root = Path(raw.get("root", ".")).resolve()
    os_style = _pick_os_style(raw.get("os", "auto"))

    out_raw = raw.get("output", {}) or {}
    output = OutputConfig(
        mode=(out_raw.get("mode", "both") or "both").strip().lower(),
        single_file=str(out_raw.get("single_file", "structure&code.txt")),
        structure_file=str(out_raw.get("structure_file", "structure.txt")),
        code_file=str(out_raw.get("code_file", "code.txt")),
    )

    cb_raw = raw.get("clipboard", {}) or {}
    clipboard = ClipboardConfig(
        enabled=bool(cb_raw.get("enabled", False)),
        text=str(cb_raw.get("text", "")),
    )

    ig_raw = raw.get("ignore", {}) or {}
    exts = frozenset(
        filter(
            None,
            map(_norm_ext, ig_raw.get("extensions", []) or [])
        )
    )
    patterns = tuple(map(str, ig_raw.get("patterns", []) or []))
    ignore = IgnoreConfig(extensions=exts, patterns=patterns)

    return Settings(root=root, os_style=os_style, output=output, clipboard=clipboard, ignore=ignore)


def _rel_path_str(root: Path, p: Path, os_style: str) -> str:
    rel = p.relative_to(root)
    style = _pick_os_style(os_style)

    # "auto": use current platform path style for display
    if style == "auto":
        return str(rel)

    parts = rel.parts
    return str(PurePosixPath(*parts)) if style == "posix" else str(PureWindowsPath(*parts))


def _should_ignore(root: Path, p: Path, s: Settings) -> bool:
    # extension ignore (your explicit requirement)
    suffix = p.suffix.lower()
    ext_ignored = suffix in s.ignore.extensions

    # optional pattern ignore (glob-like)
    rel = _rel_path_str(root, p, s.os_style)
    pat_ignored = any(fnmatch.fnmatch(rel, pat) for pat in s.ignore.patterns)

    # ignore output files if they are inside root (avoid self-including)
    out_names = frozenset({s.output.single_file, s.output.structure_file, s.output.code_file})
    self_ignored = (p.name in out_names)

    return ext_ignored or pat_ignored or self_ignored


def iter_files_and_dirs(root: Path) -> Iterable[Path]:
    # Includes root children recursively; relies on pathlib's generator.
    return root.rglob("*")


def collect_paths(root: Path, s: Settings) -> list[Path]:
    # Materialize once; allows sorting and reuse for structure + code without rescanning.
    # Filtering is done via builtins/generator expressions (no explicit for/while).
    candidates = (p for p in iter_files_and_dirs(root) if not _should_ignore(root, p, s))
    return sorted(candidates, key=lambda p: _rel_path_str(root, p, s.os_style).lower())


def _structure_lines(root: Path, paths: Iterable[Path], s: Settings) -> Iterable[str]:
    # Build a minimal tree-like indentation based on relative depth.
    def line(p: Path) -> str:
        rel = p.relative_to(root)
        depth = max(len(rel.parts) - 1, 0)
        indent = "  " * depth
        return f"{indent}{p.name}\n"

    header = ("## Project Structure\n\n",)
    body = map(line, paths)
    footer = ("\n",)
    return chain(header, body, footer)


def write_structure(out: TextIO, root: Path, paths: Iterable[Path], s: Settings) -> None:
    out.writelines(_structure_lines(root, paths, s))


def _write_file_code(out: TextIO, root: Path, p: Path, s: Settings) -> None:
    rel_str = _rel_path_str(root, p, s.os_style)
    out.write(f"// ===== File: {rel_str} =====\n")
    try:
        with p.open("rb") as f:
            # Fast streaming copy; avoids loading huge files in memory
            shutil.copyfileobj(f, out.buffer)  # type: ignore[attr-defined]
        out.write("\n\n")
    except Exception:
        out.write("// [Skipped: unreadable or non-text file]\n\n")


def write_code(out: TextIO, root: Path, paths: Iterable[Path], s: Settings) -> None:
    out.write("## Source Code\n\n")
    files = filter(lambda p: p.is_file(), paths)
    # side-effect writing via map; consume with deque-like pattern using tuple()
    tuple(map(lambda p: _write_file_code(out, root, p, s), files))


def write_outputs(s: Settings) -> Path:
    root = s.root
    paths = collect_paths(root, s)

    mode = s.output.mode
    if mode not in {"structure", "code", "both", "split"}:
        mode = "both"

    def open_text(path: Path) -> TextIO:
        return path.open("w", encoding="utf-8", newline="\n")

    if mode == "structure":
        out_path = root / s.output.single_file
        with open_text(out_path) as out:
            write_structure(out, root, paths, s)
        return out_path

    if mode == "code":
        out_path = root / s.output.single_file
        with open_text(out_path) as out:
            write_code(out, root, paths, s)
        return out_path

    if mode == "split":
        struct_path = root / s.output.structure_file
        code_path = root / s.output.code_file
        with open_text(struct_path) as out:
            write_structure(out, root, paths, s)
        with open_text(code_path) as out:
            write_code(out, root, paths, s)
        return struct_path  # return one of them as representative

    # both
    out_path = root / s.output.single_file
    with open_text(out_path) as out:
        write_structure(out, root, paths, s)
        out.write("\n")
        write_code(out, root, paths, s)
    return out_path


def copy_to_clipboard(text: str) -> bool:
    # Standard library only (tkinter). Works on Windows/macOS/Linux with GUI.
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()   # keep clipboard after app exits
        r.destroy()
        return True
    except Exception:
        return False


def main(settings_path: Optional[str] = None) -> int:
    sp = Path(settings_path or SETTINGS_FILE_DEFAULT).resolve()
    if not sp.exists():
        print(f"Settings file not found: {sp}")
        return 2

    s = load_settings(sp)
    if not s.root.exists():
        print(f"Root directory not found: {s.root}")
        return 2

    out = write_outputs(s)
    print(f"Done. Output written under: {s.root}")
    print(f"Primary output: {out}")

    if s.clipboard.enabled and s.clipboard.text.strip():
        ok = copy_to_clipboard(s.clipboard.text)
        print("Clipboard: copied" if ok else "Clipboard: failed (tkinter not available?)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
