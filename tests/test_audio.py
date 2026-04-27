import os
from unittest.mock import patch
from pdfscanner.audio import build_script, generate
from pdfscanner.extractor import Topic


def test_build_script_contains_topic_name():
    t = Topic(num=1, name="自己", sentences=["I enjoy reading books."], highlights=[])
    script = build_script(t, voice_en="Samantha")
    assert "自己" in script or "Topic 1" in script
    assert "I enjoy reading books" in script


def test_build_script_excludes_short_sentences():
    t = Topic(num=1, name="Test", sentences=["Hi.", "I enjoy long walks in the park."], highlights=[])
    script = build_script(t, voice_en="Samantha")
    assert "Hi." not in script
    assert "I enjoy long walks" in script


def test_generate_calls_say(tmp_path):
    t = Topic(num=1, name="Ads", sentences=["Advertising informs consumers."], highlights=[])
    fake_path = str(tmp_path / "Topic_01_Ads.m4a")
    # Create the file so os.path.getsize doesn't fail
    open(fake_path, "wb").close()
    with patch("pdfscanner.audio._say_to_m4a") as mock_say:
        mock_say.return_value = fake_path
        results = generate([t], output_dir=str(tmp_path))
    mock_say.assert_called_once()
    assert len(results) == 1
