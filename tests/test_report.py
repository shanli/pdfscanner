import os
from pdfscanner.report import generate
from pdfscanner.extractor import Topic


def test_generate_creates_file(tmp_path):
    topics = [
        Topic(num=1, name="Advertising",
              sentences=["Advertising informs consumers."],
              highlights=["informs", "consumers"]),
    ]
    path = generate(topics, output_dir=str(tmp_path))
    assert os.path.exists(path)


def test_markdown_contains_topic_name(tmp_path):
    topics = [Topic(num=1, name="Advertising",
                    sentences=["Ads inform us."], highlights=["inform"])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "Advertising" in content


def test_markdown_highlights_table(tmp_path):
    topics = [Topic(num=1, name="Ads",
                    sentences=[], highlights=["manipulates", "glamorous"])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "manipulates" in content
    assert "glamorous" in content
    assert "|" in content  # table format


def test_markdown_sentences_listed(tmp_path):
    topics = [Topic(num=1, name="Ads",
                    sentences=["Advertising informs consumers."], highlights=[])]
    path = generate(topics, output_dir=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "Advertising informs consumers" in content
