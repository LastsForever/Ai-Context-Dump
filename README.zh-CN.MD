# ai-context-dump

[English](README.md) | [中文](README.zh-CN.md)

把项目的目录结构与源代码汇总成适合一次性投喂 AI 的文本文件（支持单文件或分文件输出）。

---

## 功能

- 按配置的遍历根目录（`iter_root`）扫描项目
- 支持两类忽略规则（仅影响遍历与收集，不影响“怎么写输出文件”）：
  - **按文件扩展名忽略**（`ignore.extensions`）
  - **按 glob patterns 忽略**（`ignore.patterns`，fnmatch 风格）
  - 以及从部分 patterns 派生的“目录剪枝规则”（例如 `.git/*`、`bin/`）
- 支持多种输出模式：
  - **structure**：只输出结构
  - **code**：只输出代码
  - **both**：结构 + 代码输出到同一个文件
  - **split**：结构与代码分别输出到两个文件
- 可选：执行完成后把预设提示词复制到剪贴板（标准库 `tkinter`）

---

## 环境要求

- Python 3.x
- 无第三方依赖

---

## 快速开始

1. 建议放在类似路径：

```text
tools/ai-context-dump/
  ai_context_dump.py
  settings.jsonc
编辑 settings.jsonc（见下文），然后运行：

bash
python ai_context_dump.py
输出的 .txt 文件会生成在 Python 脚本所在目录（工具始终把输出写到 .py 同级目录，而不是 iter_root 下）。

配置说明
默认配置文件名为 settings.jsonc（支持全行注释）。任何以 // 或 # 开头的行都会被忽略。

iter_root（或 root）
iter_root：开始遍历的根目录（可相对/绝对）

向后兼容：如果没有 iter_root，则会回退使用旧字段 root

os
控制输出中路径分隔符展示风格：

auto：跟随当前系统

posix：使用 /

windows：使用 \

output
output.mode：structure | code | both | split

output.single_file：用于 structure | code | both

output.structure_file / output.code_file：用于 split

output.path_style：控制“给人看的路径”输出为相对或绝对：

relative：输出相对路径

absolute：输出绝对路径（Path.resolve()）

注意：无论如何配置，输出文件的写入位置始终是 .py 文件所在目录。

clipboard
clipboard.enabled：是否在导出完成后尝试复制剪贴板

clipboard.text：要复制到剪贴板的提示词

ignore
ignore.extensions：按扩展名忽略（大小写不敏感）

ignore.patterns：按 glob patterns 忽略（fnmatch 风格）

patterns 匹配规则：

如果 pattern 包含 /：按“相对路径（POSIX 形式）整体”匹配

如果 pattern 不包含 /：同时匹配

basename（文件名/目录名），以及

任意路径片段（任意层级的目录名或文件名）

目录剪枝规则（prune）：

类似 .git/、.git/*、bin/、bin/* 会被视为“忽略任意深度的同名目录及其所有内容”。

关于剪贴板
剪贴板功能使用 Python 标准库 tkinter。部分精简 Linux 环境可能未安装 tkinter，此时会提示 Clipboard: failed，但导出文件不受影响。

License
MIT
