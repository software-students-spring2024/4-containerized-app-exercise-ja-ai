"""
API module for image analysis using the DeepFace library.
This module provides functionalities to analyze images for age.
"""

from deepface import DeepFace

def analyze_image(img_path):
    """
    Analyze an image for age and gender using DeepFace.

    Parameters:
    - img_path (str): Path to the image file

    Returns:
    - list: Analysis results including age and gender
    """
    result = DeepFace.analyze(img_path=img_path, actions=['age', 'gender'])
    return [result[0]]
