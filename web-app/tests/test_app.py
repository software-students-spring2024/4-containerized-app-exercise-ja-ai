"""
Modules for getting correct pathing and correctly importing from app
"""
import sys
import os
import threading
import time
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, allowed_file, process_task

IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                           "test_png", "tester_photo.png"))

@pytest.fixture(name="testing_app")
def testing_app_fixture():
    """
    Test app for other function tests
    """
    test_app = app
    test_app.config.update({
        "TESTING": True,
    })
    yield test_app

@pytest.fixture(name="client")
def client_fixture(testing_app):
    """
    Test client for other function tests
    """
    return testing_app.test_client()

@pytest.fixture(name="task_queue")
def task_queue_fixture():
    """
    Test queue for tasks
    """
    test_queue = []
    yield test_queue

def test_allowed_file():
    """
    Test allowed_file function
    """
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
    """
    Test home function
    """
    # Test loading home page
    response = client.get('/')
    assert response.status_code == 200

def test_upload_image(client):
    """
    Test upload image page and functionality
    """
    # Test loading upload page
    response = client.get('/upload')
    assert response.status_code == 200

    # Test post request
    # Using 'with' ensures the file is open only during the operation
    with open(IMAGE_PATH, "rb") as image_file:
        # Define data and files properly
        data = {
            "age": (None, "30"),  # This is how you normally send non-file fields
            "image": (image_file, "tester_photo.png")  # Ensuring the file tuple is correct
        }
        # Flask test client handles content-type automatically here
        response = client.post("/upload", data=data)
    assert response.status_code == 400

def test_start_task(client):
    """
    Test start_task function
    """
    data = {"task_id": "12345"}
    response = client.post("/start_task", json=data)
    assert response.status_code == 202

def test_process_task(task_queue):
    """
    Test process_task function
    """
    task_queue.append("12345")
    threading.Thread(target=process_task, daemon=True).start()
    time.sleep(1)
    assert task_queue == ["12345"]

def test_get_result(client):
    """
    Test get_result function
    """
    task_id = "12345"
    response = client.get(f"/get_result/{task_id}")
    assert response.status_code == 202

    data = response.json
    assert data["task_id"] == task_id
    assert data["status" ] == "Processing"
