import pytest
from web-app.app import allowed_file

def test_allowed_file():
    # Tests cases: allowed file types
    print("Testing allowed_file function...")
    # tTest, error message (if failure)
    assert allowed_file("test.png"), "Test case failed: allowed_file('Test.png')"
    assert allowed_file("test.jpg"), "Test case failed: allowed_file('Test.jpg')"
    assert allowed_file("test.jpeg"), "Test case failed: allowed_file('Test.jpeg')"
    assert allowed_file("test.gif"), "Test case failed: allowed_file('Test.gif')"
    print("All allowed_file tests passed.")
