import pytest
from ..machine-learning-client.api import analyze_image

def test_analyze_image():
    """
    Test analyze_image function
    """
    result = analyze_image('../tester_photo.jpg')
    assert result is not None
