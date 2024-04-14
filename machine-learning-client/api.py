"""
API module for image analysis using the DeepFace library.
This module provides functionalities to analyze images for age.
"""

from deepface import DeepFace
import logging

def analyze_image(img_path):
    """
    Analyze an image for age and gender using DeepFace.

    Parameters:
    - img_path (str): Path to the image file

    Returns:
    - dict: Analysis results including age and gender
    """
    try:
        result = DeepFace.analyze(img_path=img_path, actions=['age', 'gender'])
        return result  # This returns the entire result dictionary
    except Exception as e:
        logging.error("Failed to analyze image: " + str(e))
        return None
