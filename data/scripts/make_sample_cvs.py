"""Write the synthetic persona CVs as small PDFs for the upload demo.

Reads  data/curated/personas_v2.json
Writes frontend/public/samples/<id>-<name>.pdf   (plain text PDF, Helvetica)

Every file starts with "SYNTHETIC PERSONA FOR DEMO - NOT A REAL PERSON."
No PDF library is needed: the writer below emits a minimal valid PDF.

Usage:  python data/scripts/make_sample_cvs.py
"""
from __future__ import annotations

import json
import textwrap

from _common import CURATED, ROOT

OUT = ROOT / "frontend" / "public" / "samples"
WIDTH, LINES_PER_PAGE, LEADING, TOP = 92, 52, 14, 790


def pdf_escape(s: str) -> str:
    s = s.encode("latin-1", errors="replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap(text: str) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, WIDTH, subsequent_indent="  " if para.startswith("- ") else "") or [""]
    return lines


def make_pdf(lines: list[str]) -> bytes:
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)] or [[]]
    objs: list[bytes] = [b"", b""]  # 1 catalog, 2 pages (filled below)
    font_id = 3
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    for page in pages:
        body = [f"BT /F1 10 Tf {LEADING} TL 50 {TOP} Td"]
        body += [f"({pdf_escape(line)}) Tj T*" for line in page]
        body.append("ET")
        stream = "\n".join(body).encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content_id = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (content_id, font_id))
        kids.append(len(objs))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))

    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def main() -> None:
    people = json.loads((CURATED / "personas_v2.json").read_text(encoding="utf-8"))["individual_users"]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in people:
        if not p["cv_text"].startswith("SYNTHETIC PERSONA"):
            raise SystemExit(f"{p['id']}: CV text must start with the synthetic-persona notice")
        name = f"{p['id'].lower()}-{p['name'].lower().replace(' ', '-')}.pdf"
        (OUT / name).write_bytes(make_pdf(wrap(p["cv_text"])))
        print(f"wrote frontend/public/samples/{name}")


if __name__ == "__main__":
    main()
