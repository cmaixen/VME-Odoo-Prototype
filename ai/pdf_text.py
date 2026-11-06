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


def _page_content(items, image=False):
    ops = [b"q 595 0 0 842 0 0 cm /Im1 Do Q", b"3 Tr"] if image else []
    for item in items:
        if item[0] == "line":
            _kind, x1, y1, x2, y2 = item
            ops.append(f"0.6 w {x1} {y1} m {x2} {y2} l S".encode())
            continue
        if item[0] == "row":
            # One text object with several cells: extract_pages returns them separated by tabs.
            _kind, y, size, bold, cells = item
            font = "F2" if bold else "F1"
            parts, previous = [], 0
            for x, text in cells:
                parts.append(f"{x - previous} 0 Td (".encode() + _encode(text) + b") Tj")
                previous = x
            ops.append(b"BT /" + font.encode() + f" {size} Tf {0} {y} Td ".encode() + b" ".join(parts) + b" ET")
            continue
        x, y, size, bold, text = item
        font = "F2" if bold else "F1"
        ops.append(b"BT /" + font.encode() + f" {size} Tf {x} {y} Td (".encode() + _encode(text) + b") Tj ET")
    return b"\n".join(ops)


def _stream(content, compress, extra=b""):
    if compress:
        content = zlib.compress(content)
        return b"<< /Length %d /Filter /FlateDecode%s >>\nstream\n" % (len(content), extra) + content + b"\nendstream"
    return b"<< /Length %d%s >>\nstream\n" % (len(content), extra) + content + b"\nendstream"


def write_pdf(items, compress=True):
    """One A4 page. items: (x, y, size, bold, text) for text, or ("line", x1, y1, x2, y2) for a rule."""
    return write_pages([items], compress=compress)


def write_pages(pages, compress=True, images=None):
    """A4 pages with the items of write_pdf, plus ("row", y, size, bold, [(x, text), ...]).

    images: optional JPEG per page (or None), drawn over the whole page; the text of that page is
    then invisible, like the OCR layer a scanner adds under its image.
    """
    images = images or [None] * len(pages)
    count = len(pages)
    fonts = 3 + 2 * count  # after the catalog, the page list and a page and content per page
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
            b" ".join(b"%d 0 R" % (3 + 2 * i) for i in range(count)), count),
    ]
    image_objects = []
    for index, (items, image) in enumerate(zip(pages, images)):
        xobject = b""
        if image:
            number = fonts + 2 + len(image_objects)
            image_objects.append(image)
            xobject = b" /XObject << /Im1 %d 0 R >>" % number
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
            b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >>%s >> >>" % (4 + 2 * index, fonts, fonts + 1, xobject))
        objects.append(_stream(_page_content(items, image=bool(image)), compress))
    objects += [
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    for image in image_objects:
        width, height = _jpeg_size(image)
        objects.append(
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
            b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (width, height, len(image))
            + image + b"\nendstream")
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


def _jpeg_size(data):
    """Width and height from the SOF marker of a JPEG."""
    index = 2
    while index < len(data):
        marker, length = data[index + 1], int.from_bytes(data[index + 2:index + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[index + 7:index + 9], "big"), int.from_bytes(data[index + 5:index + 7], "big")
        index += 2 + length
    raise ValueError("Geen JPEG")


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


def _block_lines(data, separator):
    lines = []
    for block in re.findall(rb"BT(.*?)ET", data, re.S):
        parts = re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", block, re.S)
        text = separator.join(_decode_string(part) for part in parts).strip()
        if text:
            lines.append(text)
    return lines


def extract_pages(pdf_bytes):
    """Text lines per page of a simple PDF made by write_pages; cells of a row are separated by a tab.

    Works for the visible text and for the invisible OCR layer of a "scanned" demo page.
    """
    objects = {int(number): body for number, body in re.findall(rb"(\d+) 0 obj\n(.*?)\nendobj", pdf_bytes, re.S)}
    kids = re.search(rb"/Kids \[([^\]]*)\]", pdf_bytes)
    pages = []
    for number in re.findall(rb"(\d+) 0 R", kids[1] if kids else b""):
        content = re.search(rb"/Contents (\d+) 0 R", objects[int(number)])
        stream = re.match(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", objects[int(content[1])], re.S)
        header, data = stream.groups()
        if b"/FlateDecode" in header:
            data = zlib.decompress(data)
        pages.append(_block_lines(data, "\t"))
    return pages
