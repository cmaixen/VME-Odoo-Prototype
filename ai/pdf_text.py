"""Write and read very simple PDFs, without extra packages.

Only for the fictitious demo files and the mock reader: write_pdf makes one-page PDFs with
Helvetica text, extract_text gets that text back. A real supplier PDF (scanned, embedded fonts)
is read by Claude, which receives the PDF itself and never goes through this module.
"""
import re
import zlib

# Characters outside Latin-1 that the demo texts use, mapped to their WinAnsi code.
WIN_ANSI = {"€": 0x80, "–": 0x96, "’": 0x92}
WIN_ANSI_REVERSE = {code: char for char, code in WIN_ANSI.items()}


def _encode(text):
    out = bytearray()
    for char in text:
        code = WIN_ANSI.get(char, ord(char))
        if code > 255:
            raise ValueError(f"Teken niet ondersteund in de demo-PDF: {char!r}")
        if char in "\\()":
            out += b"\\"
        out.append(code)
    return bytes(out)


def write_pdf(items, compress=True):
    """One A4 page. items: (x, y, size, bold, text) for text, or ("line", x1, y1, x2, y2) for a rule."""
    ops = []
    for item in items:
        if item[0] == "line":
            _kind, x1, y1, x2, y2 = item
            ops.append(f"0.6 w {x1} {y1} m {x2} {y2} l S".encode())
            continue
        x, y, size, bold, text = item
        font = "F2" if bold else "F1"
        ops.append(b"BT /" + font.encode() + f" {size} Tf {x} {y} Td (".encode() + _encode(text) + b") Tj ET")
    content = b"\n".join(ops)
    stream_dict = b"<< /Length %d >>" % len(content)
    if compress:
        content = zlib.compress(content)
        stream_dict = b"<< /Length %d /Filter /FlateDecode >>" % len(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        stream_dict + b"\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(pdf)


def _decode_string(raw):
    """Body of a PDF literal string (between the parentheses) to text."""
    out = []
    index = 0
    while index < len(raw):
        byte = raw[index]
        if byte == 0x5C and index + 1 < len(raw):  # backslash
            nxt = raw[index + 1:index + 2]
            octal = re.match(rb"[0-7]{1,3}", raw[index + 1:index + 4])
            if octal:
                out.append(int(octal[0], 8))
                index += 1 + len(octal[0])
                continue
            out.append({b"n": 10, b"r": 13, b"t": 9}.get(nxt, nxt[0]))
            index += 2
            continue
        out.append(byte)
        index += 1
    return "".join(WIN_ANSI_REVERSE.get(code) or chr(code) for code in out)


def extract_text(pdf_bytes):
    """Text lines of a simple PDF: one line per text object (BT ... ET), in the order written."""
    lines = []
    for match in re.finditer(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        header, data = match.groups()
        if b"/FlateDecode" in header:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                continue
        for block in re.findall(rb"BT(.*?)ET", data, re.S):
            parts = re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", block, re.S)
            text = "".join(_decode_string(part) for part in parts).strip()
            if text:
                lines.append(text)
    return lines
