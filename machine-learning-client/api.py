"""
API module for image analysis using the DeepFace library.
This module provides functionalities to analyze images for age.
"""

import logging
from deepface import DeepFace

logging.basicConfig(level=logging.INFO)


def analyze_image(img_path):
    """
    Analyze an image for age and gender using DeepFace.

    Parameters:
        img_path (str): Path to the image file

    Returns:
        list: Analysis results including age
    """
    try:
        logging.info("Analyzing the image at path: %s", img_path)
        result = DeepFace.analyze(img_path=img_path, actions=["age"])
        logging.info("Analysis result: %s", result)
        return result[0]["age"]
    except Exception as e:
        logging.error("An error occurred during image analysis: %s", e)
        raise
