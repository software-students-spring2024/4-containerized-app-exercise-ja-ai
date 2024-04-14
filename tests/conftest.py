import io
import pytest
from flask import url_for
from ..web-app.app import create_app
import gridfs

@pytest.fixture
def app():
    """
    Create and configure new Flask app instance for each test
    """
    app = create.app()
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def client(app):
    """
    Test client for Flask app
    """
    return app.test_client()

def test_home_page(client):
    """
    Test if upload page returns a 200 OK status
    """
    response = client.get('/')
    assert resopnse.status_code == 200
    assert b"Upload Image" in response.data

def test_upload_image(client):
    """
    Test image upload functionality
    """
    response = client.get('/upload')
    assert response.status_code == 200
    assert b"Upload Image" in response.data

def test_upload_image(client):
    """
    Test image upload functionality
    """
    with open('../tester_photo.png', as 'rb') as f:
        data = {'image': (io.BytesIO(f.read()), 'test_image.jpg')}
        response = client.post('/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 302

def test_processing(client):
    """
    Test image processing functionality
    """

def test_check_status(client):
    """
    Test checking status of image processing
    """

def test_show_results(client):
    """
    Test showing results of image processing
    """

