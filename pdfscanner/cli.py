from __future__ import annotations
import argparse
import sys
import os
from pdfscanner.extractor import open_pdf, extract, is_text_based


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfscanner",
        description="Extract topics, audio, and highlights from PDF files.",
    )
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="Scan a PDF and produce outputs")

    scan.add_argument("pdf", metavar="PDF", help="Path to PDF file")
    scan.add_argument("--start-page", type=int, default=1,
                      help="Start page, 1-based (default: 1)")
    scan.add_argument("--end-page", type=int, default=None,
                      help="End page, 1-based (default: last page)")
    scan.add_argument("--topics", type=str, default=None,
                      help='Comma-separated topic numbers or names, e.g. "1,2,Advertising"')
    scan.add_argument("--ocr", action="store_true",
                      help="Force Apple Vision OCR (default: auto-detect)")
    scan.add_argument("--password", type=str, default=None,
                      help="PDF password")
    scan.add_argument("--audio", action="store_true",
                      help="Generate M4A audio per topic")
    scan.add_argument("--markdown", action="store_true",
                      help="Generate Markdown vocabulary report")
    scan.add_argument("--output", type=str, default="./output",
                      help="Output directory (default: ./output)")
    scan.add_argument("--voice-en", type=str, default="Samantha",
                      help="English TTS voice (default: Samantha)")
    scan.add_argument("--voice-zh", type=str, default="Tingting",
                      help="Chinese TTS voice (default: Tingting)")
    scan.add_argument("--workers", type=int, default=8,
                      help="Parallel say processes (default: 8)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command != "scan":
        parser.print_help()
        sys.exit(0)

    if not args.audio and not args.markdown:
        print("Error: specify at least one output flag: --audio, --markdown", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.pdf):
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # Convert 1-based page numbers to 0-based
    start = args.start_page - 1
    end = (args.end_page - 1) if args.end_page else None

    topic_filter = [t.strip() for t in args.topics.split(",")] if args.topics else None

    ocr_fn = None
    if args.ocr:
        from pdfscanner.ocr import recognize_page
        ocr_fn = recognize_page

    print(f"Opening: {args.pdf}")
    try:
        doc = open_pdf(args.pdf, password=args.password)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    text_mode = not args.ocr and is_text_based(doc)
    print(f"Mode: {'text' if text_mode else 'OCR'} | Pages {args.start_page}–{args.end_page or len(doc)}")

    print("Extracting topics...")
    topics = extract(
        doc,
        start_page=start,
        end_page=end,
        topic_filter=topic_filter,
        force_ocr=args.ocr,
        ocr_fn=ocr_fn,
    )

    if not topics:
        print("Warning: no topics found in the specified page range.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(topics)} topic(s):")
    for t in topics:
        print(f"  Topic {t.num} 《{t.name}》: {len(t.sentences)} sentences, {len(t.highlights)} highlights")

    os.makedirs(args.output, exist_ok=True)

    if args.audio:
        print("\nGenerating audio...")
        from pdfscanner.audio import generate as gen_audio
        gen_audio(topics, output_dir=args.output, voice_en=args.voice_en, workers=args.workers)

    if args.markdown:
        print("\nGenerating Markdown...")
        from pdfscanner.report import generate as gen_report
        gen_report(topics, output_dir=args.output)

    print(f"\nDone. Files saved to: {args.output}")
