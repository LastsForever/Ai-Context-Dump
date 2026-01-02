#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Iterable, List, Set, Tuple


DEFAULT_SETTINGS_FILE = "settings.jsonc"


# ----------------------------
# Settings parsing (JSON + full-line comments)
# ----------------------------

def load_json_with_comments(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    cleaned = "\n".join(
        line for line in lines
        if not line.lstrip().startswith(("//", "#"))
    )
    return json.loads(cleaned)


def to_posix(s: str) -> str:
    return s.replace("\\", "/")


def norm_ext(ext: str) -> str:
    e = (ext or "").strip().lower()
    if not e:
        return ""
    return e if e.startswith(".") else f".{e}"


# ----------------------------
# Settings models
# ----------------------------

@dataclass(frozen=True)
class OutputConfig:
    mode: str                 # structure | code | both | split
    single_file: str
    structure_file: str
    code_file: str
    path_style: str           # relative | absolute


@dataclass(frozen=True)
class ClipboardConfig:
    enabled: bool
    text: str


@dataclass(frozen=True)
class IgnoreConfig:
    extensions: frozenset[str]
    patterns: Tuple[str, ...]
    dir_rules: Tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    iter_root: Path
    os_style: str
    output: OutputConfig
    clipboard: ClipboardConfig
    ignore: IgnoreConfig


# ----------------------------
# Settings loading
# ----------------------------

def derive_dir_rules(patterns: Iterable[str]) -> Tuple[str, ...]:
    rules: List[str] = []
    for pat in patterns:
        p = to_posix((pat or "").strip())
        if not p:
            continue
        if p.endswith("/*"):
            rules.append(p[:-2])
        elif p.endswith("/"):
            rules.append(p[:-1])
    return tuple(rules)


def load_settings(settings_path: Path) -> Settings:
    raw = load_json_with_comments(settings_path)

    iter_root = Path(raw.get("iter_root", raw.get("root", "."))).resolve()
    os_style = (raw.get("os", "auto") or "auto").strip().lower()

    out_raw = raw.get("output", {}) or {}
    output = OutputConfig(
        mode=(out_raw.get("mode", "both") or "both").strip().lower(),
        single_file=str(out_raw.get("single_file", "structure&code.txt")),
        structure_file=str(out_raw.get("structure_file", "structure.txt")),
        code_file=str(out_raw.get("code_file", "code.txt")),
        path_style=(out_raw.get("path_style", "relative") or "relative").strip().lower(),
    )

    cb_raw = raw.get("clipboard", {}) or {}
    clipboard = ClipboardConfig(
        enabled=bool(cb_raw.get("enabled", False)),
        text=str(cb_raw.get("text", "")),
    )

    ig_raw = raw.get("ignore", {}) or {}
    exts = frozenset(
        filter(None, (norm_ext(x) for x in (ig_raw.get("extensions", []) or [])))
    )
    patterns = tuple(str(x) for x in (ig_raw.get("patterns", []) or []))
    dir_rules = derive_dir_rules(patterns)

    ignore = IgnoreConfig(extensions=exts, patterns=patterns, dir_rules=dir_rules)
    return Settings(iter_root, os_style, output, clipboard, ignore)


# ----------------------------
# Path formatting helpers
# ----------------------------

def format_rel(root: Path, p: Path, os_style: str) -> str:
    rel = p.relative_to(root)
    if os_style == "windows":
        return str(PureWindowsPath(*rel.parts))
    if os_style == "posix":
        return str(PurePosixPath(*rel.parts))
    return str(rel)


def format_output_path(p: Path, script_root: Path, style: str) -> str:
    if style == "absolute":
        return str(p.resolve())
    try:
        return str(p.relative_to(script_root))
    except ValueError:
        return str(p.resolve())


# ----------------------------
# Ignore logic
# ----------------------------

def match_pattern(rel_posix: str, parts: Tuple[str, ...], basename: str, pat: str) -> bool:
    rp = rel_posix.lower()
    bn = basename.lower()
    pt = to_posix(pat).lower()

    if "/" in pt:
        return fnmatch.fnmatch(rp, pt)

    if fnmatch.fnmatch(bn, pt):
        return True
    return any(fnmatch.fnmatch(seg.lower(), pt) for seg in parts)


def is_pruned_dir(dirname: str, s: Settings) -> bool:
    dn = dirname.lower()
    return any(fnmatch.fnmatch(dn, to_posix(rule).lower()) for rule in s.ignore.dir_rules)


def is_ignored_path(iter_root: Path, p: Path, s: Settings, settings_filename: str) -> bool:
    if p.name == settings_filename:
        return True

    rel_posix = str(PurePosixPath(*p.relative_to(iter_root).parts))
    parts = tuple(rel_posix.split("/"))

    if p.is_file() and p.suffix.lower() in s.ignore.extensions:
        return True

    return any(match_pattern(rel_posix, parts, p.name, pat) for pat in s.ignore.patterns)


# ----------------------------
# Collect
# ----------------------------

def collect(iter_root: Path, s: Settings, settings_filename: str):
    dirs: Set[Path] = set()
    files: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(iter_root):
        cur_dir = Path(dirpath)

        if cur_dir != iter_root and is_ignored_path(iter_root, cur_dir, s, settings_filename):
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in dirnames if not is_pruned_dir(d, s)]
        dirs.add(cur_dir)

        for name in filenames:
            fp = cur_dir / name
            if not is_ignored_path(iter_root, fp, s, settings_filename):
                files.append(fp)

    files.sort(key=lambda p: str(PurePosixPath(*p.relative_to(iter_root).parts)).lower())
    return dirs, files


# ----------------------------
# Structure rendering
# ----------------------------

def build_index(iter_root: Path, dirs: Set[Path], files: List[Path]):
    idx: Dict[Path, List[Path]] = {}

    def add(parent: Path, child: Path):
        idx.setdefault(parent, []).append(child)

    for d in dirs:
        if d != iter_root and d.parent in dirs:
            add(d.parent, d)

    for f in files:
        if f.parent in dirs:
            add(f.parent, f)

    for k in idx:
        idx[k].sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))

    return idx


def render_structure(iter_root: Path, idx: Dict[Path, List[Path]]):
    lines = ["## Project structure\n\n", f"{iter_root.name}/\n"]

    def rec(node: Path, depth: int):
        for ch in idx.get(node, []):
            lines.append("  " * depth + ch.name + ("/" if ch.is_dir() else "") + "\n")
            if ch.is_dir():
                rec(ch, depth + 1)

    rec(iter_root, 1)
    lines.append("\n")
    return lines


# ----------------------------
# File dumping
# ----------------------------

def dump_file(out, iter_root: Path, f: Path, s: Settings):
    rel = format_rel(iter_root, f, s.os_style)
    path_display = rel if s.output.path_style == "relative" else str(f.resolve())

    out.write(f"//\n//\t# File Path: {path_display} #\n//\n\n")
    try:
        out.write(f.read_text(encoding="utf-8"))
    except Exception:
        out.write("// [Skipped: unreadable or binary file]\n")
    out.write("\n\n")


# ----------------------------
# Writers
# ----------------------------

def write_structure_only(path: Path, iter_root: Path, idx):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.writelines(render_structure(iter_root, idx))


def write_code_only(path: Path, iter_root: Path, files, s: Settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write("## Files\n\n")
        for f in files:
            dump_file(out, iter_root, f, s)


def write_both_single(path: Path, iter_root: Path, idx, files, s: Settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.writelines(render_structure(iter_root, idx))
        out.write("## Files\n\n")
        for f in files:
            dump_file(out, iter_root, f, s)


# ----------------------------
# Clipboard
# ----------------------------

def copy_to_clipboard(text: str) -> bool:
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        return False


# ----------------------------
# Main
# ----------------------------

def main(settings_file: str = DEFAULT_SETTINGS_FILE) -> int:
    sp = Path(settings_file).resolve()
    if not sp.exists():
        print(f"Settings file not found: {sp}")
        return 2

    s = load_settings(sp)
    iter_root = s.iter_root
    script_root = Path(__file__).resolve().parent

    dirs, files = collect(iter_root, s, sp.name)
    idx = build_index(iter_root, dirs, files)

    generated: List[Path] = []

    if s.output.mode == "structure":
        p = script_root / s.output.single_file
        write_structure_only(p, iter_root, idx)
        generated.append(p)

    elif s.output.mode == "code":
        p = script_root / s.output.single_file
        write_code_only(p, iter_root, files, s)
        generated.append(p)

    elif s.output.mode == "split":
        p1 = script_root / s.output.structure_file
        p2 = script_root / s.output.code_file
        write_structure_only(p1, iter_root, idx)
        write_code_only(p2, iter_root, files, s)
        generated.extend([p1, p2])

    else:
        p = script_root / s.output.single_file
        write_both_single(p, iter_root, idx, files, s)
        generated.append(p)

    if s.clipboard.enabled and s.clipboard.text.strip():
        print("Clipboard:", "copied" if copy_to_clipboard(s.clipboard.text) else "failed")

    print("Generated txt files:")
    for p in generated:
        print(" -", format_output_path(p, script_root, s.output.path_style))

    print("ai-context-dump finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
