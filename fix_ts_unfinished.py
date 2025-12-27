# -*- coding: utf-8 -*-
"""
Batch-fix Qt .ts "unfinished" flags safely (no manual editing).

Default behavior:
- For <translation type="unfinished"> that already contains non-empty text (or <numerusform> children),
  remove the "type" attribute (mark as finished).

Optional:
- --fill-empty-with-source: for empty unfinished translations, copy <source> text into <translation>
  and mark as finished (useful for quick placeholders).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple


def _is_non_empty_translation(tr: ET.Element) -> bool:
    # Handle plain text
    if (tr.text or "").strip():
        return True
    # Handle plural forms: <numerusform>...</numerusform>
    for ch in list(tr):
        if ch.tag == "numerusform" and (ch.text or "").strip():
            return True
    return False


def _preset_watch(locale: str) -> Dict[str, str]:
    locale = (locale or "").strip().lower()
    if locale in ("zh_cn", "zh-hans", "zh-hans-cn", "cn"):
        return {
            "Watch / Memory(&M)...": "监视/内存(&M)...",
            "Watch / Memory": "监视/内存",
            "Watch module is not available.\n\nPlease ensure dependencies are installed (pyelftools).\n\nError: %s": "Watch 模块不可用。\n\n请确认已安装依赖（pyelftools）。\n\n错误：%s",
            "Found existing JLink connection, closing it first...": "发现已有 JLink 连接，先关闭...",
            "Closing existing JLink connection...": "正在关闭已有 JLink 连接...",
            "Retrying JLink connection...": "正在重试 JLink 连接...",
            "Select MAP and ELF to enable.": "请选择 MAP 和 ELF 以启用。",
            "Select...": "选择...",
            "MAP": "MAP",
            "ELF": "ELF",
            "Off": "关闭",
            "Refresh": "刷新",
            "Reload Symbols": "重新加载符号",
            "Refresh Now": "立即刷新",
            "Expression / symbol name": "表达式/符号名",
            "Add": "添加",
            "Expression": "表达式",
            "Value": "值",
            "Remove": "移除",
            "View Memory": "查看内存",
            "Load": "加载",
            "Address": "地址",
            "Size": "大小",
            "Select MAP file": "选择 MAP 文件",
            "Select ELF file": "选择 ELF 文件",
            "Error": "错误",
            "DWARF Parse Failed": "DWARF 解析失败",
            "ELF DWARF parsing failed, Watch will run in MAP-only mode.\n\nStruct field expansion will be unavailable.\n\nError: %s": "ELF DWARF 解析失败，Watch 将以仅 MAP 模式运行。\n\n结构体字段展开将不可用。\n\n错误：%s",
            "Watch": "监视",
            "Please select MAP and ELF, then click Reload Symbols.": "请先选择 MAP 和 ELF，然后点击“重新加载符号”。",
            "symbol not found": "未找到符号",
            "address is 0 (not placed)": "地址为 0（未放置）",
            "No active JLink": "无活动 JLink",
            "Invalid address": "地址无效",
        }
    if locale in ("zh_tw", "zh-hant", "zh-hant-tw", "tw"):
        return {
            "Watch / Memory(&M)...": "監視/記憶體(&M)...",
            "Watch / Memory": "監視/記憶體",
            "Watch module is not available.\n\nPlease ensure dependencies are installed (pyelftools).\n\nError: %s": "Watch 模組不可用。\n\n請確認已安裝相依套件（pyelftools）。\n\n錯誤：%s",
            "Found existing JLink connection, closing it first...": "發現既有 JLink 連線，先關閉...",
            "Closing existing JLink connection...": "正在關閉既有 JLink 連線...",
            "Retrying JLink connection...": "正在重試 JLink 連線...",
            "Select MAP and ELF to enable.": "請選擇 MAP 與 ELF 以啟用。",
            "Select...": "選擇...",
            "MAP": "MAP",
            "ELF": "ELF",
            "Off": "關閉",
            "Refresh": "刷新",
            "Reload Symbols": "重新載入符號",
            "Refresh Now": "立即刷新",
            "Expression / symbol name": "運算式/符號名稱",
            "Add": "新增",
            "Expression": "運算式",
            "Value": "值",
            "Remove": "移除",
            "View Memory": "檢視記憶體",
            "Load": "載入",
            "Address": "位址",
            "Size": "大小",
            "Select MAP file": "選擇 MAP 檔案",
            "Select ELF file": "選擇 ELF 檔案",
            "Error": "錯誤",
            "DWARF Parse Failed": "DWARF 解析失敗",
            "ELF DWARF parsing failed, Watch will run in MAP-only mode.\n\nStruct field expansion will be unavailable.\n\nError: %s": "ELF DWARF 解析失敗，Watch 將以僅 MAP 模式運行。\n\n結構體欄位展開將不可用。\n\n錯誤：%s",
            "Watch": "監視",
            "Please select MAP and ELF, then click Reload Symbols.": "請先選擇 MAP 與 ELF，然後點擊「重新載入符號」。",
            "symbol not found": "找不到符號",
            "address is 0 (not placed)": "位址為 0（未放置）",
            "No active JLink": "無活動的 JLink",
            "Invalid address": "位址無效",
        }
    return {}


def process_ts(path: Path, fill_empty_with_source: bool, preset: str = "", locale: str = "") -> Tuple[int, int, int, int]:
    """
    Returns (total_unfinished, cleaned_unfinished, filled_from_source, filled_from_preset).
    """
    tree = ET.parse(str(path))
    root = tree.getroot()

    total = 0
    cleaned = 0
    filled = 0
    preset_filled = 0

    preset_map: Dict[str, str] = {}
    if (preset or "").strip().lower() == "watch":
        # Infer locale from filename if not provided
        loc = (locale or "").strip()
        if not loc:
            p = str(path).lower()
            if "zh_cn" in p:
                loc = "zh_CN"
            elif "zh_tw" in p:
                loc = "zh_TW"
        preset_map = _preset_watch(loc)

    for ctx in root.findall("context"):
        for msg in ctx.findall("message"):
            src = msg.find("source")
            tr = msg.find("translation")
            if tr is None:
                continue
            if tr.get("type") != "unfinished":
                continue
            total += 1

            src_text = (src.text if src is not None else "") or ""
            if preset_map and src_text in preset_map:
                # Overwrite unfinished translation with preset text and mark as finished
                for ch in list(tr):
                    tr.remove(ch)
                tr.text = preset_map[src_text]
                tr.attrib.pop("type", None)
                preset_filled += 1
                continue

            if _is_non_empty_translation(tr):
                # Already translated, just clear unfinished flag
                try:
                    del tr.attrib["type"]
                except Exception:
                    tr.attrib.pop("type", None)
                cleaned += 1
                continue

            if fill_empty_with_source:
                tr.text = src_text
                try:
                    del tr.attrib["type"]
                except Exception:
                    tr.attrib.pop("type", None)
                filled += 1

    tree.write(str(path), encoding="utf-8", xml_declaration=True)
    return total, cleaned, filled, preset_filled


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-p",
        "--path",
        action="append",
        default=[],
        help="TS file path. Can be passed multiple times. If omitted, defaults to ./lang/*.ts",
    )
    ap.add_argument("--fill-empty-with-source", action="store_true", help="Fill empty unfinished translations with <source> text.")
    ap.add_argument("--preset", default="", help="Apply preset translations for unfinished entries. Supported: watch")
    ap.add_argument("--locale", default="", help="Preset locale: zh_CN or zh_TW (optional; can be inferred from filename).")
    ap.add_argument("--backup", action="store_true", help="Create .bak backup before writing.")
    ap.add_argument("--dry-run", action="store_true", help="Only print stats, do not write files.")
    args = ap.parse_args(argv)

    if args.path:
        ts_files = [Path(p) for p in args.path]
    else:
        ts_files = sorted(Path("lang").glob("*.ts"))

    if not ts_files:
        print("No .ts files found.")
        return 1

    for p in ts_files:
        if not p.exists():
            print(f"[SKIP] Not found: {p}")
            continue

        if args.backup:
            ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            bak = p.with_suffix(p.suffix + f".{ts}.bak")
            shutil.copyfile(p, bak)
            print(f"[BACKUP] {bak}")

        if args.dry_run:
            # Parse and count without writing
            tree = ET.parse(str(p))
            root = tree.getroot()
            total = 0
            translated = 0
            for ctx in root.findall("context"):
                for msg in ctx.findall("message"):
                    tr = msg.find("translation")
                    if tr is None:
                        continue
                    if tr.get("type") != "unfinished":
                        continue
                    total += 1
                    if _is_non_empty_translation(tr):
                        translated += 1
            print(f"[DRY] {p}: unfinished={total}, already_translated={translated}")
            continue

        total, cleaned, filled, preset_filled = process_ts(
            p,
            bool(args.fill_empty_with_source),
            preset=str(args.preset or ""),
            locale=str(args.locale or ""),
        )
        print(f"[OK] {p}: unfinished={total}, cleared_flag={cleaned}, filled_from_source={filled}, filled_from_preset={preset_filled}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


