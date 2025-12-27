from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from elftools.elf.elffile import ELFFile
from elftools.elf.constants import SHN_INDICES
from elftools.elf.enums import ENUM_ST_INFO_TYPE


@dataclass(frozen=True)
class TypeDesc:
    kind: str  # 'base'|'pointer'|'array'|'struct'|'typedef'|'enum'|'unknown'
    name: str
    size: int
    # struct
    members: Tuple["StructMember", ...] = ()
    # pointer/array
    target: Optional["TypeDesc"] = None
    count: Optional[int] = None


@dataclass(frozen=True)
class StructMember:
    name: str
    offset: int  # bytes
    typ: TypeDesc


@dataclass(frozen=True)
class DwarfVariable:
    name: str
    address: int
    typ: TypeDesc


def _attr_int(die, attr_name: str) -> Optional[int]:
    a = die.attributes.get(attr_name)
    if not a:
        return None
    try:
        return int(a.value)
    except Exception:
        return None


def _attr_str(die, attr_name: str) -> Optional[str]:
    a = die.attributes.get(attr_name)
    if not a:
        return None
    try:
        v = a.value
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="ignore")
        return str(v)
    except Exception:
        return None


def _die_ref(die, attr_name: str):
    a = die.attributes.get(attr_name)
    if not a:
        return None
    return a.value


def _decode_location_addr(die) -> Optional[int]:
    """Handle the common case: DW_AT_location = DW_OP_addr <addr>."""
    loc = die.attributes.get("DW_AT_location")
    if not loc:
        return None
    try:
        raw = loc.value
        if isinstance(raw, (bytes, bytearray)) and len(raw) >= 1:
            # DW_OP_addr = 0x03
            if raw[0] == 0x03:
                # address size depends on ELF class; elftools provides stream size,
                # but many Cortex-M are 32-bit little-endian.
                # Try 4 then 8.
                if len(raw) >= 1 + 4:
                    addr = int.from_bytes(raw[1:5], "little", signed=False)
                    if addr != 0:
                        return addr
                if len(raw) >= 1 + 8:
                    addr = int.from_bytes(raw[1:9], "little", signed=False)
                    if addr != 0:
                        return addr
    except Exception:
        return None
    return None


def _decode_uleb128(data: Union[bytes, bytearray], start: int = 0) -> Tuple[int, int]:
    """Return (value, next_index)."""
    result = 0
    shift = 0
    i = start
    while i < len(data):
        b = data[i]
        result |= (b & 0x7F) << shift
        i += 1
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, i


def _decode_sleb128(data: Union[bytes, bytearray], start: int = 0) -> Tuple[int, int]:
    """Return (value, next_index)."""
    result = 0
    shift = 0
    i = start
    size = 8 * 8
    b = 0
    while i < len(data):
        b = data[i]
        result |= (b & 0x7F) << shift
        shift += 7
        i += 1
        if (b & 0x80) == 0:
            break
    if (shift < size) and (b & 0x40):
        result |= - (1 << shift)
    return result, i


def _decode_member_offset(die) -> int:
    """DW_AT_data_member_location may be int or exprloc; handle common exprloc patterns."""
    a = die.attributes.get("DW_AT_data_member_location")
    if not a:
        return 0
    try:
        v = a.value
        if isinstance(v, int):
            return int(v)
        if isinstance(v, (bytes, bytearray)) and len(v) >= 1:
            op = v[0]
            # Common:
            # DW_OP_plus_uconst (0x23) <uleb>
            # DW_OP_constu (0x10) <uleb>
            # DW_OP_consts (0x11) <sleb>
            if op == 0x23:
                val, _ = _decode_uleb128(v, 1)
                return int(val)
            if op == 0x10:
                val, _ = _decode_uleb128(v, 1)
                return int(val)
            if op == 0x11:
                val, _ = _decode_sleb128(v, 1)
                return int(val)
    except Exception:
        return 0
    return 0


class DwarfIndex:
    def __init__(self, elf_path: str):
        self.elf_path = elf_path
        self._types_by_die_offset: Dict[int, TypeDesc] = {}
        self._vars_by_name: Dict[str, DwarfVariable] = {}
        self._var_types_by_name: Dict[str, TypeDesc] = {}
        self._sym_addr_by_name: Dict[str, Tuple[int, int]] = {}  # name -> (addr, size)

        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            if not elf.has_dwarf_info():
                raise RuntimeError("ELF has no DWARF info")
            self._sym_addr_by_name = self._load_object_symbols(elf)
            # Cortex-M/embedded ELFs often don't need relocation for DWARF, and some toolchains
            # emit relocation records that pyelftools cannot handle (e.g. "Unsupported relocation type: 0").
            # Disable relocation to improve compatibility.
            dwarf = elf.get_dwarf_info(relocate_dwarf_sections=False)
            for cu in dwarf.iter_CUs():
                top = cu.get_top_DIE()
                self._index_cu(top, cu)

    def _load_object_symbols(self, elf: ELFFile) -> Dict[str, Tuple[int, int]]:
        out: Dict[str, Tuple[int, int]] = {}
        for sec_name in (".symtab", ".dynsym"):
            sec = elf.get_section_by_name(sec_name)
            if not sec:
                continue
            try:
                for sym in sec.iter_symbols():
                    try:
                        st_type = sym["st_info"]["type"]
                    except Exception:
                        st_type = None
                    # Only object/data symbols
                    if st_type != "STT_OBJECT":
                        continue
                    name = sym.name
                    if not name:
                        continue
                    addr = int(sym["st_value"] or 0)
                    size = int(sym["st_size"] or 0)
                    if addr == 0:
                        continue
                    out.setdefault(name, (addr, size))
                    # Best-effort normalize leading underscore
                    if name.startswith("_"):
                        out.setdefault(name[1:], (addr, size))
            except Exception:
                continue
        return out

    def _index_cu(self, top_die, cu):
        for die in top_die.iter_children():
            self._visit_die(die, cu)

    def _visit_die(self, die, cu):
        tag = die.tag
        if tag == "DW_TAG_variable":
            name = _attr_str(die, "DW_AT_name") or _attr_str(die, "DW_AT_linkage_name")
            if name:
                t = self.resolve_type(die)
                if t:
                    self._var_types_by_name.setdefault(name, t)
                addr = _decode_location_addr(die)
                if addr is None:
                    sym = self._sym_addr_by_name.get(name)
                    if sym:
                        addr = sym[0]
                if addr is not None and t:
                    self._vars_by_name.setdefault(name, DwarfVariable(name=name, address=addr, typ=t))

        # Recurse
        for ch in die.iter_children():
            self._visit_die(ch, cu)

    def resolve_type(self, die) -> Optional[TypeDesc]:
        # Follow DW_AT_type reference from variable/typedef/member
        tref = die.attributes.get("DW_AT_type")
        if not tref:
            return None
        try:
            ref = tref.value
            # elftools stores reference as offset within CU; DIE offset is absolute
            # We can use dwarfinfo.get_DIE_from_refaddr but we don't keep dwarfinfo here.
            # Instead: elftools DIE has method get_DIE_from_attribute via CU.
            tdie = die.get_DIE_from_attribute("DW_AT_type")
            return self._resolve_type_die(tdie)
        except Exception:
            return None

    def _resolve_type_die(self, tdie) -> TypeDesc:
        off = getattr(tdie, "offset", None)
        if isinstance(off, int) and off in self._types_by_die_offset:
            return self._types_by_die_offset[off]

        tag = tdie.tag
        name = _attr_str(tdie, "DW_AT_name") or ""

        # Base / typedef / pointer / array / struct
        if tag == "DW_TAG_base_type":
            size = _attr_int(tdie, "DW_AT_byte_size") or 0
            t = TypeDesc(kind="base", name=name or "base", size=size)
        elif tag == "DW_TAG_typedef":
            base = tdie.get_DIE_from_attribute("DW_AT_type")
            target = self._resolve_type_die(base)
            size = target.size
            t = TypeDesc(kind="typedef", name=name or target.name, size=size, target=target)
        elif tag == "DW_TAG_pointer_type":
            size = _attr_int(tdie, "DW_AT_byte_size") or 4
            target = None
            try:
                base = tdie.get_DIE_from_attribute("DW_AT_type")
                target = self._resolve_type_die(base)
            except Exception:
                target = None
            t = TypeDesc(kind="pointer", name=name or "ptr", size=size, target=target)
        elif tag == "DW_TAG_array_type":
            target = None
            try:
                base = tdie.get_DIE_from_attribute("DW_AT_type")
                target = self._resolve_type_die(base)
            except Exception:
                target = TypeDesc(kind="unknown", name="unknown", size=0)
            count = None
            for ch in tdie.iter_children():
                if ch.tag == "DW_TAG_subrange_type":
                    ub = _attr_int(ch, "DW_AT_upper_bound")
                    if ub is not None:
                        count = ub + 1
                        break
                    cnt = _attr_int(ch, "DW_AT_count")
                    if cnt is not None:
                        count = cnt
                        break
            size = (target.size * count) if (target and target.size and count) else 0
            t = TypeDesc(kind="array", name=name or "array", size=size, target=target, count=count)
        elif tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
            size = _attr_int(tdie, "DW_AT_byte_size") or 0
            members: List[StructMember] = []
            # Placeholder to break recursion for self-referential structs
            t = TypeDesc(kind="struct", name=name or "struct", size=size, members=())
            if isinstance(off, int):
                self._types_by_die_offset[off] = t
            for ch in tdie.iter_children():
                if ch.tag != "DW_TAG_member":
                    continue
                mname = _attr_str(ch, "DW_AT_name") or ""
                moff = _decode_member_offset(ch)
                mtype = None
                try:
                    mtype_die = ch.get_DIE_from_attribute("DW_AT_type")
                    mtype = self._resolve_type_die(mtype_die)
                except Exception:
                    mtype = TypeDesc(kind="unknown", name="unknown", size=0)
                members.append(StructMember(name=mname, offset=moff, typ=mtype))
            t = TypeDesc(kind="struct", name=name or "struct", size=size, members=tuple(members))
        else:
            size = _attr_int(tdie, "DW_AT_byte_size") or 0
            t = TypeDesc(kind="unknown", name=name or tag, size=size)

        if isinstance(off, int):
            self._types_by_die_offset[off] = t
        return t

    @property
    def variables(self) -> Dict[str, DwarfVariable]:
        return self._vars_by_name

    def lookup(self, name: str) -> Optional[DwarfVariable]:
        v = self._vars_by_name.get(name)
        if v:
            return v
        # If we have type but address comes from symtab, synthesize
        t = self._var_types_by_name.get(name)
        sym = self._sym_addr_by_name.get(name)
        if t and sym:
            return DwarfVariable(name=name, address=sym[0], typ=t)
        # Try base form (strip ".<digits>") and leading underscore
        try:
            import re
            base = re.sub(r"\.\d+$", "", name)
            if base != name:
                v = self._vars_by_name.get(base)
                if v:
                    return v
                t = self._var_types_by_name.get(base)
                sym = self._sym_addr_by_name.get(base)
                if t and sym:
                    return DwarfVariable(name=base, address=sym[0], typ=t)
            if name.startswith("_"):
                alt = name[1:]
                v = self._vars_by_name.get(alt)
                if v:
                    return v
                t = self._var_types_by_name.get(alt)
                sym = self._sym_addr_by_name.get(alt)
                if t and sym:
                    return DwarfVariable(name=alt, address=sym[0], typ=t)
        except Exception:
            pass
        return None


