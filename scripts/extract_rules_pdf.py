#!/usr/bin/env python
"""Extract readable text from the official Twilight Struggle PDFs.

The rules and the FAQ are the arbiter for every rules question in this
engine, and reading them found ten defects in a day. They are also GMT
Games' copyrighted work, so the text itself is *not* committed here -- see
`docs/RULES_SOURCES.md` for the rulings this engine depends on, quoted
briefly with citations. This script is how you get the full text locally.

    curl -o /tmp/ts-rules.pdf https://www.gmtgames.com/living_rules/TS_Rules_Deluxe.pdf
    curl -o /tmp/ts-faq.pdf   https://www.gmtgames.com/nnts/FAQv5.pdf
    python scripts/extract_rules_pdf.py /tmp/ts-faq.pdf --faq > /tmp/faq.txt

Written against the stdlib alone (no pypdf) because the project has no PDF
dependency and does not want one for a developer-only tool. It walks the
raw stream objects: FlateDecode streams are inflated, unfiltered streams
read as-is, and DCTDecode (JPEG) skipped. Text comes from the parenthesised
literals of the content streams, which is enough for searching and quoting
and is not a faithful layout reconstruction -- expect run-together words at
line ends and no column ordering.

`--faq` additionally splits the result into Q/A pairs, which is the shape
the FAQ is actually written in and much easier to grep.
"""
from __future__ import annotations

import argparse
import re
import sys
import zlib
from pathlib import Path

_INFLATERS = (
    lambda blob: zlib.decompress(blob),
    lambda blob: zlib.decompressobj().decompress(blob),
    lambda blob: zlib.decompressobj(-15).decompress(blob),  # raw deflate
)


def _inflate(blob: bytes) -> bytes | None:
    for attempt in _INFLATERS:
        try:
            return attempt(blob)
        except Exception:
            continue
    return None


def stream_text(raw: bytes) -> list[str]:
    """The text of every content stream, in file order."""
    chunks = []
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        header = raw[max(0, match.start() - 400):match.start()]
        filt = re.search(rb"/Filter\s*/(\w+)", header)
        name = filt.group(1) if filt else b""
        if name == b"DCTDecode":
            continue  # an image
        data = _inflate(raw[start:end]) if name == b"FlateDecode" else raw[start:end]
        if not data or (b"Tj" not in data and b"TJ" not in data):
            continue
        parts = []
        for literal in re.finditer(rb"\((?:\\.|[^\\()])*\)", data):
            text = re.sub(rb"\\([()\\])", rb"\1", literal.group(0)[1:-1])
            parts.append(text.decode("latin-1"))
        chunks.append("".join(parts))
    return chunks


def readable(chunks: list[str]) -> str:
    """Drop the chunks that are font tables and other binary rather than
    prose: a content stream's text is nearly all letters, spaces and light
    punctuation, and nothing else here is."""
    kept = []
    for chunk in chunks:
        for line in chunk.split("\n"):
            if len(line) < 20:
                continue
            prose = sum(c.isalpha() or c.isspace() or c in ".,;:'\"()-/?!#" for c in line)
            if prose / len(line) > 0.9:
                kept.append(line)
    return re.sub(r"\s+", " ", "\n".join(kept))


def qa_pairs(text: str) -> list[str]:
    """The FAQ's Q./A. pairs. Card sections are marked "# 47 Junta"."""
    flat = re.sub(r"\s+", " ", text)
    return re.findall(r"(Q\..{20,600}?A\..{20,700}?)(?=Q\.|#\s*\d|$)", flat)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", help="a locally downloaded rules or FAQ PDF")
    parser.add_argument("--faq", action="store_true",
                        help="also split into Q/A pairs, one per line")
    parser.add_argument("--stats", action="store_true", help="report coverage instead")
    args = parser.parse_args(argv)

    raw = Path(args.pdf).read_bytes()
    chunks = stream_text(raw)
    text = readable(chunks)
    if args.stats:
        pairs = qa_pairs(text)
        cards = {int(m.group(1)) for m in re.finditer(r"#\s*(\d{1,3})\s+[A-Z]",
                                                      re.sub(r"\s+", " ", text))}
        print(f"{len(chunks)} text streams, {len(text)} chars, "
              f"{len(pairs)} Q/A pairs, {len(cards)} card sections")
        return 0
    if args.faq:
        for pair in qa_pairs(text):
            print(pair)
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
