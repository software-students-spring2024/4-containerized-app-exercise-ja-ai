"""
Need to import these for pytest to work
"""
import os
from unittest.mock import MagicMock
import pytest
import api
from deepface import DeepFace

# Define the path to a sample image for testing
IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                           "test_png", "tester_photo2.png"))

def test_analyze_image():
    """
    Test to see if analyze image returns an age, not necessarily the correct one
    """
    # Mock the DeepFace library's analyze method
    api.DeepFace.analyze = MagicMock(return_value=[{"age": 30}])

    # Call the analyze_image function with the sample image path
    result = api.analyze_image(IMAGE_PATH)

    # Assert that the result is as expected
    assert result == 30
