import os


def test_still_fails():
    candidate = os.environ["THESEUS_CANDIDATE"]
    content = open(candidate).read()
    assert "def fibonacci" in content
