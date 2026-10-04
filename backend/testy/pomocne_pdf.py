# -*- coding: utf-8 -*-

from __future__ import annotations


def _escapuj(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def sestav_pdf(stranky: list[list[str]]) -> bytes:
    objekty: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    odkazy_stranek: list[int] = []
    for radky in stranky:
        obsah = "BT /F1 11 Tf 14 TL 72 760 Td\n" + "".join(
            f"({_escapuj(r)}) Tj T*\n" for r in radky
        ) + "ET"
        data = obsah.encode("cp1252")
        objekty.append(
            b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n"
            + data + b"\nendstream"
        )
        cislo_obsahu = len(objekty)
        objekty.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(cislo_obsahu).encode() + b" 0 R >>"
        )
        odkazy_stranek.append(len(objekty))

    kids = " ".join(f"{c} 0 R" for c in odkazy_stranek)
    objekty[1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(odkazy_stranek)} >>"
    ).encode()

    vystup = bytearray(b"%PDF-1.4\n")
    posuny: list[int] = []
    for cislo, telo in enumerate(objekty, 1):
        posuny.append(len(vystup))
        vystup += f"{cislo} 0 obj\n".encode() + telo + b"\nendobj\n"
    zacatek_xref = len(vystup)
    vystup += f"xref\n0 {len(objekty) + 1}\n0000000000 65535 f \n".encode()
    for posun in posuny:
        vystup += f"{posun:010d} 00000 n \n".encode()
    vystup += (
        f"trailer\n<< /Size {len(objekty) + 1} /Root 1 0 R >>\n"
        f"startxref\n{zacatek_xref}\n%%EOF\n"
    ).encode()
    return bytes(vystup)
