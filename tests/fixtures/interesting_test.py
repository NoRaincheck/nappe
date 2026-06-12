import sys


def test_still_fails():
    candidate = sys.argv[1]
    content = open(candidate).read()
    assert "def fibonacci" in content
