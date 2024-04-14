import pytest
from web-app.app import allowed_file

def test_allowed_file():
    # Tests cases: allowed file types
    print("Testing allowed_file function...")
    # tTest, error message (if failure)
    assert allowed_file("test.png") == True, "Test case failed: allowed_file('test.png')"
    assert allowed_file("test.jpg") == True, "Test case failed: allowed_file('test.jpg')"
    assert allowed_file("test.jpeg") == True, "Test case failed: allowed_file('test.jpeg')"
    assert allowed_file("test.gif") == True, "Test case failed: allowed_file('test.gif')"
    assert allowed_file("test.txt") == False, "Test case failed: allowed_File('test.txt')"
    print("All allowed_file tests passed.")
