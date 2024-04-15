import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web_app")))

from app import create_app

@pytest.fixture
def app():
    """
    Create and configure new Flask app instance for each test
    """
    app = create_app()
    app.config['TESTING'] = True
    yield app

@pytest.fixture
def client(app):
    """
    Test client for Flask app
    """
    return app.test_client()
