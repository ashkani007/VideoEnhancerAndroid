#!/usr/bin/env python3
"""Google Play 16 KB page-size check for the 64-bit native libraries in an APK.

For every lib/arm64-v8a/*.so and lib/x86_64/*.so:
  * every ELF PT_LOAD segment must be aligned to >= 16 KB (p_align >= 0x4000);
  * if the library is stored uncompressed, its data must start at a 16 KB
    offset in the zip (so it can be mapped directly).
Exits 1 if any 64-bit library fails. 32-bit ABIs are listed but not enforced.
"""
import struct
import sys
import zipfile

PAGE = 0x4000
ABIS_64 = ("arm64-v8a", "x86_64")


def load_alignments(data: bytes):
    if data[:4] != b"\x7fELF":
        return None
    is64 = data[4] == 2
    endian = "<" if data[5] == 1 else ">"
    if is64:
        phoff, = struct.unpack_from(endian + "Q", data, 0x20)
        phentsize, phnum = struct.unpack_from(endian + "HH", data, 0x36)
    else:
        phoff, = struct.unpack_from(endian + "I", data, 0x1C)
        phentsize, phnum = struct.unpack_from(endian + "HH", data, 0x2A)
    aligns = []
    for i in range(phnum):
        off = phoff + i * phentsize
        p_type, = struct.unpack_from(endian + "I", data, off)
        if p_type != 1:  # PT_LOAD
            continue
        if is64:
            p_align, = struct.unpack_from(endian + "Q", data, off + 0x30)
        else:
            p_align, = struct.unpack_from(endian + "I", data, off + 0x1C)
        aligns.append(p_align)
    return aligns


def data_offset(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    zf.fp.seek(info.header_offset)
    header = zf.fp.read(30)
    name_len, extra_len = struct.unpack_from("<HH", header, 26)
    return info.header_offset + 30 + name_len + extra_len


def main(path: str) -> int:
    failures = 0
    with zipfile.ZipFile(path) as zf:
        libs = [i for i in zf.infolist() if i.filename.startswith("lib/") and i.filename.endswith(".so")]
        if not libs:
            print("no native libraries")
            return 0
        for info in sorted(libs, key=lambda i: i.filename):
            abi = info.filename.split("/")[1]
            aligns = load_alignments(zf.read(info)) or []
            min_align = min(aligns) if aligns else 0
            stored = info.compress_type == zipfile.ZIP_STORED
            zip_ok = (not stored) or data_offset(zf, info) % PAGE == 0
            ok = min_align >= PAGE and zip_ok
            enforced = abi in ABIS_64
            status = "OK" if ok else ("FAIL" if enforced else "n/a (32-bit)")
            print(f"{status:14} {info.filename:55} LOAD align {hex(min_align):8} "
                  f"{'stored' if stored else 'compressed'}{'' if zip_ok else ' (zip offset not 16 KB aligned)'}")
            if enforced and not ok:
                failures += 1
    print(f"{failures} 64-bit librar{'y' if failures == 1 else 'ies'} not 16 KB compatible")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
