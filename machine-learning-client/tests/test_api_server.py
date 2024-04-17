"""
Need these modules for the tests to work
"""
import sys
import os
import pytest
from api_server import app


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                           "test_png", "tester_photo2.png"))

@pytest.fixture(name="testing_app")
def testing_app_fixture():
    """
    Fixture to provide Flask application for testing
    """
    test_app = app
    test_app.config.update({
        "TESTING": True,
    })
    yield test_app

@pytest.fixture(name="client")
def client_fixture(testing_app):
    """
    Fixture to create a test client for the Flask app
    """
    # Set up the Flask app for testing
    return testing_app.test_client()

def test_analyze_success(client, mocker):
    """
    Test the analyze endpoint with a successful analysis
    """
    # Mock the analyze_image function to return a dummy result
    mocker.patch("api_server.analyze_image", return_value={"age": 25})

    # Create a temporary file and send it as part of the request
    with open(IMAGE_PATH, "rb") as image_file:
        data = {
            "age": (None, "25"),
            "image": (image_file, "tester_photo.png")
        }
        response = client.post("analyze", data=data)

    # Check that the response status code is 200 and the result matches the expected value
    assert response.status_code == 200
    assert response.json == {"age": 25}
