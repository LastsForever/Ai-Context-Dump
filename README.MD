# ai-context-dump

[English](README.md) | [中文](README.zh-CN.md)

Dump a project’s directory structure and source code into AI-friendly text files.

---

## What it does

- Walks a configured root directory
- Filters files using:
  - ignored extensions
  - optional glob patterns
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
  ai-context-dump.settings.json
Run:

bash
python ai_context_dump.py
Check generated outputs under the configured root directory.

Settings
Edit ai-context-dump.settings.json:

root: root directory to scan

os: auto | posix | windows (controls how paths are rendered in the dump)

output.mode:

structure

code

both

split

clipboard.enabled: copy prompt text to clipboard after generation

clipboard.text: the prompt to copy

ignore.extensions: ignored file extensions (e.g. .dll, .png)

ignore.patterns: optional glob-style ignore patterns (e.g. bin/*)

Notes on clipboard
Clipboard uses Python standard library tkinter. On some minimal Linux environments, tkinter may be missing; in that case, the tool will simply print Clipboard: failed.

License
MIT

代码

---

## README（中文版）：`README.zh-CN.md`

```markdown
# ai-context-dump

[English](README.md) | [中文](README.zh-CN.md)

把项目的目录结构与源代码汇总成适合一次性投喂 AI 的文本文件。

---

## 功能

- 按配置的根目录扫描项目
- 支持两类忽略规则：
  - **按文件扩展名忽略**（你的核心诉求）
  - **可选的 glob patterns 忽略**
- 支持多种输出模式：
  - **structure**：只输出结构
  - **code**：只输出代码
  - **both**：结构 + 代码输出到同一个文件
  - **split**：结构与代码分别输出到两个文件
- 可选：执行完成后把预设“问 AI 的提示词”复制到剪贴板（标准库 `tkinter`）

---

## 环境要求

- Python 3.x
- 无第三方依赖

---

## 快速开始

1. 建议放在：

```text
tools/ai-context-dump/
  ai_context_dump.py
  ai-context-dump.settings.json
运行：

bash
python ai_context_dump.py
在 settings.json 里配置的 root 目录下查看输出文件。

配置说明
编辑 ai-context-dump.settings.json：

root：开始迭代的根目录

os：auto | posix | windows（仅影响输出文件中路径分隔符的展示）

output.mode：

structure

code

both

split

clipboard.enabled：是否复制提示词到剪贴板

clipboard.text：复制到剪贴板的提示词内容

ignore.extensions：忽略的文件扩展名（例如 .dll、.png）

ignore.patterns：可选 glob 忽略规则（例如 bin/*）

关于剪贴板
剪贴板功能使用 Python 标准库 tkinter。某些精简 Linux 环境可能未安装 tkinter，此时会提示 Clipboard: failed，但导出不受影响。

License
MIT

