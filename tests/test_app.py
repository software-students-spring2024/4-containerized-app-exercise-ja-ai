import pytest
import bson
import gridfs
import sys
import os
from flask import Flask

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web_app")))

IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tester_photo.png"))

from app import allowed_file

print(allowed_file)
print(type(allowed_file))

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

def test_home(client):
    """
    Testing home route
    """
    response = client.get('/')
    assert response.status_code == 200
    assert b'Welcome' in response.data

def test_upload_image(client):
    """
    Test upload_image route
    """
    response = client.get('/upload')
    assert response.status_code == 200

def test_processing(client):
    """
    Test processing route
    """
    with open(IMAGE_PATH, "rb") as image_file:
        response = client.get('/processing/tester_photo.png', data={'image': image_file})

    assert response.status_code == 200
    assert b'Success' in resonse.data

def test_check_status(client):
    """
    Test check_status route
    """
    with open(IMAGE_PATH, "rb") as image_file:
        response = client.get("/processing/tester_photo.png")
    assert response.status_code == 200
    assert b'pending' in response.data

def test_show_results(client):
    """
    Test show_results route
    """
    response = client.get('/results/123.jpg')
    assert response.status_code == 302
