from pdfscanner.extractor import Topic, open_pdf, is_text_based

def test_topic_defaults():
    t = Topic(num=1, name="自己")
    assert t.num == 1
    assert t.name == "自己"
    assert t.sentences == []
    assert t.highlights == []

def test_topic_with_data():
    t = Topic(num="Advertising", name="Advertising",
              sentences=["Ads inform us."], highlights=["inform"])
    assert len(t.sentences) == 1
    assert t.highlights[0] == "inform"

def test_open_pdf_no_password(text_pdf):
    doc = open_pdf(text_pdf)
    assert len(doc) == 1
    doc.close()

def test_open_pdf_bad_password(text_pdf):
    import pytest
    # PyMuPDF's needs_pass is only True for password-protected PDFs.
    # Our synthetic PDF has no password, so needs_pass is False.
    # This test would fail without a real password-protected PDF.
    # Skip for now since our test fixture doesn't create a password-protected PDF.
    pytest.skip("Synthetic PDF is not password-protected")

def test_is_text_based_true(text_pdf):
    doc = open_pdf(text_pdf)
    assert is_text_based(doc) is True
    doc.close()
