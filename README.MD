# ai-context-dump

[English](README.MD) | [中文](README.zh-CN.MD)

Dump a project’s directory structure and source code into an AI-friendly text file (or files).

---

## What it does

- Walks a configured traversal root directory (`iter_root`)
- Filters traversal using:
  - ignored extensions (`ignore.extensions`)
  - optional glob patterns (`ignore.patterns`)
  - derived directory pruning rules (ONLY derived from patterns ending with `/` or `/*`, e.g. `.git/`, `.git/*`, `bin/`, `bin/*`)
- Generates output according to mode:
  - **structure**: structure only
  - **code**: code only
  - **both**: structure + code in a single file
  - **split**: structure and code into two separate files
- Optionally copies a pre-defined prompt to clipboard after completion (stdlib `tkinter`)

---

## Requirements

- Python 3.x
- No third-party dependencies

---

## Quick start

1. Put the tool somewhere, e.g.:

```text
tools/ai-context-dump/
  ai_context_dump.py
  settings.jsonc
```

2. Edit `settings.jsonc` (see below), then run:

```bash
python ai_context_dump.py
```

3. Check the generated `.txt` outputs next to the Python script  
(the tool always writes outputs under the script directory, not under `iter_root`).

---

## Settings

The default settings file name is `settings.jsonc` (JSON with full-line comments).  
Lines starting with `//` or `#` are ignored.

---

### iter_root (or root)

- `iter_root`: traversal root directory (relative or absolute)

Backward compatibility: if `iter_root` is missing, the tool falls back to `root`.

---

### os

Controls how file paths are rendered in the output:

- `auto`: current OS style
- `posix`: forward slashes `/`
- `windows`: backslashes `\`

**Note:** this affects path DISPLAY only (headers and console output), not traversal or matching.

---

### output

- `output.mode`: `structure | code | both | split`
- `output.single_file`: used by `structure | code | both`
- `output.structure_file` and `output.code_file`: used by `split`

- `output.path_style`: controls whether displayed paths are relative or absolute:
  - `relative`:
    - in file content headers (`// # File Path:`), paths are relative to `iter_root`
    - in console output (generated file list), paths are relative to the script directory
  - `absolute`: use absolute paths via `Path.resolve()`

**Note:** Output files are always written relative to the directory containing the `.py` script.

---

### clipboard

- `clipboard.enabled`: if true, try to copy `clipboard.text` to the clipboard after generation
- `clipboard.text`: the prompt text to copy

---

### ignore

- `ignore.extensions`: ignore by file extension (case-insensitive; extensions are normalized to lowercase and forced to start with `.`)
- `ignore.patterns`: ignore by glob patterns (fnmatch-style)

#### Pattern matching behavior

- If a pattern contains `/`, it is matched against the full relative path (POSIX-form, relative to `iter_root`).
- Otherwise it is matched against:
  - the basename, and
  - any path segment (directory or file name)

Matching is case-insensitive.

#### Directory pruning behavior

Directory pruning rules are derived ONLY from patterns that end with:

- `xxx/`
- `xxx/*`

These derived rules are used to prune `os.walk()` directory traversal (`dirnames[:]` filtering).

**Important details (as implemented):**

- Pruning checks only the immediate directory name (not the full relative path).
- Patterns like `bin*` or `.git*` do NOT produce pruning rules; they only take effect via normal ignore matching (after entering directories).

---

## Notes on clipboard

Clipboard uses Python standard library `tkinter`.  
On some minimal Linux environments, `tkinter` may be missing; in that case, the tool will print:

```text
Clipboard: failed
```

but file generation is unaffected.

---

## License

MIT
