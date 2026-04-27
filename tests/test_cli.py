import pytest
from unittest.mock import patch
from pdfscanner.cli import build_parser, main


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["scan", "report.pdf"])
    assert args.pdf == "report.pdf"
    assert args.start_page == 1
    assert args.end_page is None
    assert args.ocr is False
    assert args.audio is False
    assert args.markdown is False
    assert args.output == "./output"
    assert args.voice_en == "Samantha"
    assert args.voice_zh == "Tingting"
    assert args.workers == 8


def test_parser_all_options():
    parser = build_parser()
    args = parser.parse_args([
        "scan", "file.pdf",
        "--start-page", "5", "--end-page", "10",
        "--topics", "1,2,Advertising",
        "--ocr", "--password", "secret",
        "--audio", "--markdown",
        "--output", "/tmp/out",
        "--voice-en", "Alex",
        "--voice-zh", "Mei-Jia",
        "--workers", "4",
    ])
    assert args.start_page == 5
    assert args.end_page == 10
    assert args.topics == "1,2,Advertising"
    assert args.ocr is True
    assert args.password == "secret"
    assert args.audio is True
    assert args.markdown is True
    assert args.output == "/tmp/out"
    assert args.workers == 4


def test_main_no_output_flags(tmp_path, text_pdf):
    """Running without --audio or --markdown exits with code 1."""
    with patch("sys.argv", ["pdfscanner", "scan", text_pdf,
                            "--output", str(tmp_path)]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 1
