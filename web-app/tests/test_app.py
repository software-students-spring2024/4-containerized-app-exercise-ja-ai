import pytest
from app import app, allowed_file

@pytest.fixture()
def testing_app():
    """
    Test app for other function tests
    """
    test_app = app
    test_app.config.update({
        "TESTING": True,
    })
    yield test_app

@pytest.fixture()
def client(testing_app):
    """
    Test client for other function tests
    """
    return testing_app.test_client()

def test_allowed_file():
    # Tests cases: allowed file types
    print("Testing allowed_file function...")
    # tTest, error message (if failure)
    assert allowed_file("test.png"), "Test case failed: allowed_file('Test.png')"
    assert allowed_file("test.jpg"), "Test case failed: allowed_file('Test.jpg')"
    assert allowed_file("test.jpeg"), "Test case failed: allowed_file('Test.jpeg')"
    assert allowed_file("test.gif"), "Test case failed: allowed_file('Test.gif')"
    assert not allowed_file("test.txt"), "Test case failed: allowed_file('Test.txt')"
    print("All allowed_file tests passed.")

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    
