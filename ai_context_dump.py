#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Tuple, Dict, Optional

# ==========================================
# 1. 基础辅助
# ==========================================
class Util:
    @staticmethod
    def to_posix(s: str) -> str:
        return s.replace('\\', '/')

    @staticmethod
    def norm_ext(s: str) -> str:
        t = s.strip().lower()
        if not t: return ""
        return t if t.startswith(".") else "." + t

    @staticmethod
    def glob_to_regex(pattern: str) -> str:
        # 模仿 F# 中的 globToRegex 实现
        sb = ["^"]
        for c in pattern:
            if c == '*': sb.append(".*")
            elif c == '?': sb.append(".")
            elif c in ".()+|^$@%": sb.append("\\" + c)
            else: sb.append(c)
        sb.append("$")
        return "".join(sb)

# ==========================================
# 2. 配置模型
# ==========================================
@dataclass
class OutputConfig:
    mode: str
    single_file: str
    structure_file: str
    code_file: str
    path_style: str

@dataclass
class ClipboardConfig:
    enabled: bool
    text: str

@dataclass
class IgnoreConfig:
    extensions: Set[str]
    patterns: List[str]
    dir_rules: List[str]

@dataclass
class Settings:
    iter_root: str
    os_style: str
    output: OutputConfig
    clipboard: ClipboardConfig
    ignore: IgnoreConfig

# ==========================================
# 3. 配置加载
# ==========================================
module_json_config = None # 命名占位

def load_settings(path: str) -> Settings:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 过滤注释
    cleaned_json = "".join([l for l in lines if not l.lstrip().startswith(("//", "#"))])
    root = json.loads(cleaned_json)

    def get_prop(d, keys, default):
        for k in keys:
            if k in d: return d[k]
        return default

    iter_root = os.path.abspath(get_prop(root, ["iter_root", "root"], "."))
    os_style = str(root.get("os", "auto")).strip().lower()

    out_el = root.get("output", {})
    output = OutputConfig(
        mode=str(out_el.get("mode", "both")).lower(),
        single_file=out_el.get("single_file", "structure&code.txt"),
        structure_file=out_el.get("structure_file", "structure.txt"),
        code_file=out_el.get("code_file", "code.txt"),
        path_style=str(out_el.get("path_style", "relative")).lower()
    )

    cb_el = root.get("clipboard", {})
    clipboard = ClipboardConfig(
        enabled=bool(cb_el.get("enabled", False)),
        text=str(cb_el.get("text", ""))
    )

    ig_el = root.get("ignore", {})
    raw_patterns = ig_el.get("patterns", [])
    
    dir_rules = []
    for p in raw_patterns:
        p2 = Util.to_posix(p.strip())
        if p2.endswith("/*"): dir_rules.append(p2[:-2])
        elif p2.endswith("/"): dir_rules.append(p2[:-1])

    extensions = {Util.norm_ext(x) for x in ig_el.get("extensions", [])}

    return Settings(
        iter_root=iter_root,
        os_style=os_style,
        output=output,
        clipboard=clipboard,
        ignore=IgnoreConfig(extensions, raw_patterns, dir_rules)
    )

# ==========================================
# 4. 核心逻辑
# ==========================================
def match_pattern(rel_posix: str, parts: List[str], basename: str, pat: str) -> bool:
    rp = rel_posix.lower()
    bn = basename.lower()
    pt = Util.to_posix(pat).lower()
    regex_str = Util.glob_to_regex(pt)
    
    if "/" in pt:
        return bool(re.match(regex_str, rp, re.IGNORECASE))
    else:
        if re.match(regex_str, bn, re.IGNORECASE): return True
        return any(re.match(regex_str, p.lower(), re.IGNORECASE) for p in parts)

def is_pruned_dir(dirname: str, s: Settings) -> bool:
    dn = Util.to_posix(dirname).lower()
    for rule in s.ignore.dir_rules:
        if re.match(Util.glob_to_regex(rule.lower()), dn, re.IGNORECASE):
            return True
    return False

def is_ignored_path(iter_root: str, p: str, s: Settings, settings_filename: str) -> bool:
    name = os.path.basename(p)
    if name == settings_filename: return True
    
    rel = os.path.relpath(p, iter_root)
    rel_posix = Util.to_posix(rel)
    parts = rel_posix.split('/')
    
    if not os.path.isdir(p):
        ext = Util.norm_ext(os.path.splitext(p)[1])
        if ext in s.ignore.extensions: return True
    
    return any(match_pattern(rel_posix, parts, name, pat) for pat in s.ignore.patterns)

def collect(iter_root: str, s: Settings, settings_filename: str):
    all_files = []
    
    # 检查根目录是否被忽略
    root_ignored = is_ignored_path(os.path.dirname(iter_root), iter_root, s, settings_filename)
    if root_ignored:
        return [], True

    for root, dirs, files in os.walk(iter_root):
        # 这里的 dirs[:] 修改会影响 walk 的后续遍历 (Pruning)
        dirs[:] = [d for d in dirs if not is_pruned_dir(d, s) and 
                   not is_ignored_path(iter_root, os.path.join(root, d), s, settings_filename)]
        
        for f in files:
            full_path = os.path.join(root, f)
            if not is_ignored_path(iter_root, full_path, s, settings_filename):
                all_files.append(full_path)

    all_files.sort(key=lambda x: Util.to_posix(os.path.relpath(x, iter_root)).lower())
    return all_files, False

# ==========================================
# 5. 树形结构生成
# ==========================================
def build_index(iter_root: str, files: List[str]):
    idx = {}
    full_root = os.path.abspath(iter_root).rstrip(os.sep)

    for f in files:
        current_child = os.path.abspath(f).rstrip(os.sep)
        while True:
            parent = os.path.dirname(current_child).rstrip(os.sep)
            if parent not in idx: idx[parent] = set()
            idx[parent].add(current_child)
            
            if parent.lower() == full_root.lower() or len(parent) <= len(full_root):
                break
            current_child = parent

    # 排序：文件夹在前，文件在后
    sorted_idx = {}
    for parent, children in idx.items():
        child_list = list(children)
        child_list.sort(key=lambda x: (
            not os.path.isdir(x), 
            os.path.basename(x).lower()
        ))
        sorted_idx[parent] = child_list
    return sorted_idx

def render_structure(iter_root: str, idx: Dict[str, List[str]]) -> List[str]:
    lines = ["## Project structure\n\n"]
    full_root = os.path.abspath(iter_root).rstrip(os.sep)
    
    if idx:
        lines.append(os.path.basename(full_root) + "/\n")
        def rec(node: str, depth: int):
            node_full = os.path.abspath(node).rstrip(os.sep)
            if node_full in idx:
                for child in idx[node_full]:
                    indent = "  " * depth
                    suffix = "/" if os.path.isdir(child) else ""
                    lines.append(f"{indent}{os.path.basename(child)}{suffix}\n")
                    if os.path.isdir(child):
                        rec(child, depth + 1)
        rec(full_root, 1)
    else:
        lines.append("[No files matching the criteria]\n")
    
    lines.append("\n")
    return lines

# ==========================================
# 6. 文件内容处理与 IO
# ==========================================
def dump_file(iter_root: str, s: Settings, file: str) -> str:
    rel = os.path.relpath(file, iter_root)
    if s.os_style == "windows": rel = rel.replace('/', '\\')
    elif s.os_style == "posix": rel = rel.replace('\\', '/')
    
    path_display = os.path.abspath(file) if s.output.path_style == "absolute" else rel
    header = f"//\n//\t# File Path: {path_display} #\n//\n\n"
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        content = "// [Skipped: unreadable or binary file]\n"
    return header + content + "\n\n"

def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
        elif sys.platform == "darwin":
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
        else:
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=text)
        return process.returncode == 0
    except:
        return False

# ==========================================
# 8. 应用程序逻辑 (App)
# ==========================================
def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4.0)

def run():
    args = sys.argv[1:]
    settings_file = args[0] if args else "settings.jsonc"
    settings_path = os.path.abspath(settings_file)

    if not os.path.exists(settings_path):
        print(f"Settings file not found: {settings_path}", file=sys.stderr)
        return 2

    s = load_settings(settings_path)
    files, root_ignored = collect(s.iter_root, s, os.path.basename(settings_path))

    if root_ignored:
        print(f"Error: Iteration root '{s.iter_root}' is ignored.", file=sys.stderr)
        return 3

    idx = build_index(s.iter_root, files)
    struct_lines = render_structure(s.iter_root, idx)
    
    code_contents = [dump_file(s.iter_root, s, f) for f in files]
    all_code_lines = ["## Files\n\n"] + code_contents

    report_data = []

    def safe_write(file_name, lines):
        if not file_name: return
        full_out = os.path.join(os.getcwd(), file_name)
        os.makedirs(os.path.dirname(full_out), exist_ok=True)
        content = "".join(lines)
        with open(full_out, 'w', encoding='utf-8') as f:
            f.write(content)
        report_data.append((file_name, content))

    # 写入逻辑
    mode = s.output.mode
    if mode == "structure":
        safe_write(s.output.single_file, struct_lines)
    elif mode == "code":
        safe_write(s.output.single_file, all_code_lines)
    elif mode == "split":
        safe_write(s.output.structure_file, struct_lines)
        safe_write(s.output.code_file, all_code_lines)
    else:
        safe_write(s.output.single_file, struct_lines + all_code_lines)

    # 剪贴板
    if s.clipboard.enabled and s.clipboard.text.strip():
        copy_to_clipboard(s.clipboard.text)

    # 控制台输出 (与 F# 完全一致)
    print("================================  ai-context-dump ================================")
    print("Generated files report:\n")
    for name, content in report_data:
        print(f" - Path: {name}")
        print(f"   Chars: {len(content)}")
        print(f"   Tokens: ~{estimate_tokens(content)}\n")
    
    print("ai-context-dump finished successfully.")
    print("==================================================================================")
    return 0

if __name__ == "__main__":
    sys.exit(run())