import pytest
import fitz


@pytest.fixture
def text_pdf(tmp_path):
    """A simple text-based PDF with two numbered sections."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "1. Advertising", fontsize=14)
    page.insert_text((50, 80), "Advertising informs consumers.", fontsize=11)
    page.insert_text((50, 110), "2. Animal Rights", fontsize=14)
    page.insert_text((50, 140), "Animals deserve protection.", fontsize=11)
    path = str(tmp_path / "sample.pdf")
    doc.save(path)
    doc.close()
    return path
