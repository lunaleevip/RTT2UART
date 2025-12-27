import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class MapSymbol:
    name: str
    address: int
    size: int
    section: str


_SECTION_HEADER_RE = re.compile(r"^\s*\.(?P<section>bss|data|rodata)\.(?P<secname>\S+)\s*$")
_SECTION_INLINE_RE = re.compile(
    # .data.app_nv   0x0000000020007e08        0x4 Output/.../app_config.o
    r"^\s*\.(?P<section>bss|data|rodata)\.(?P<secname>\S+)\s+"
    r"0x(?P<addr>[0-9A-Fa-f]+)\s+0x(?P<size>[0-9A-Fa-f]+)\b"
)
_ADDR_SIZE_LINE_RE = re.compile(
    #                0x0000000020007db8       0x10 Output/.../gsensor_common.o
    r"^\s*0x(?P<addr>[0-9A-Fa-f]+)\s+0x(?P<size>[0-9A-Fa-f]+)\b"
)
_SYMBOL_ADDR_LINE_RE = re.compile(
    #                0x0000000020007db8                gsensor_cfg
    r"^\s*0x(?P<addr>[0-9A-Fa-f]+)\s+(?P<sym>\S+)\s*$"
)


def parse_segger_map(map_path: str) -> Dict[str, MapSymbol]:
    """Parse SEGGER Embedded Studio .map and return symbol->MapSymbol (global/static variables).

    Notes:
    - The .map contains many entries with address 0; we ignore address==0
    - SES map has 2 common patterns:
      1) inline:   .bss.foo  0xADDR  0xSIZE  obj.o
      2) 3-line:  .data.foo
                 0xADDR  0xSIZE obj.o
                 0xADDR        foo
    - Names may contain suffix like ".123"; we keep full name and also add best-effort base name mapping.
    """
    symbols: Dict[str, MapSymbol] = {}
    base_symbols: Dict[str, MapSymbol] = {}

    pending: Optional[Tuple[str, str, Optional[int], Optional[int]]] = None
    # pending = (section, secname, addr, size)

    with open(map_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("*fill*") or s.startswith("LOAD") or s.startswith("START GROUP") or s.startswith("END GROUP"):
                continue

            m_inline = _SECTION_INLINE_RE.match(line)
            if m_inline:
                section = m_inline.group("section")
                secname = m_inline.group("secname")
                addr = int(m_inline.group("addr"), 16)
                size = int(m_inline.group("size"), 16)
                pending = (section, secname, addr, size)
                # Often this represents a variable even without a following "symbol name" line.
                if addr != 0 and size != 0:
                    _add_symbol(symbols, base_symbols, secname, addr, size, section)
                continue

            m_head = _SECTION_HEADER_RE.match(line)
            if m_head:
                section = m_head.group("section")
                secname = m_head.group("secname")
                pending = (section, secname, None, None)
                continue

            m_as = _ADDR_SIZE_LINE_RE.match(line)
            if m_as and pending:
                section, secname, addr0, size0 = pending
                if addr0 is None and size0 is None:
                    addr = int(m_as.group("addr"), 16)
                    size = int(m_as.group("size"), 16)
                    pending = (section, secname, addr, size)
                    # Also add secname as a symbol candidate
                    if addr != 0 and size != 0:
                        _add_symbol(symbols, base_symbols, secname, addr, size, section)
                continue

            m_sym = _SYMBOL_ADDR_LINE_RE.match(line)
            if m_sym and pending:
                section, secname, addr0, size0 = pending
                addr = int(m_sym.group("addr"), 16)
                symname = m_sym.group("sym")
                size = int(size0 or 0)
                if addr != 0:
                    _add_symbol(symbols, base_symbols, symname, addr, size, section)
                # Clear pending once we consumed the symbol name line
                pending = None
                continue

    # Prefer exact; fallback to base name for convenience.
    merged = dict(base_symbols)
    merged.update(symbols)
    return merged


def lookup_symbol(symbols: Dict[str, MapSymbol], name: str) -> Optional[MapSymbol]:
    if not name:
        return None
    if name in symbols:
        return symbols[name]
    # Also try stripping common prefixes
    n = name.strip()
    return symbols.get(n)


def _add_symbol(symbols: Dict[str, MapSymbol], base_symbols: Dict[str, MapSymbol], name: str, addr: int, size: int, section: str) -> None:
    if not name:
        return
    if addr == 0:
        return
    sym = MapSymbol(name=name, address=addr, size=int(size or 0), section=section)
    symbols[name] = sym

    base = re.sub(r"\.\d+$", "", name)
    if base and base not in base_symbols:
        base_symbols[base] = sym


