# machine-learning-client/api.py

from deepface import DeepFace

def analyze_image(img_path):
    """Analyze an image for age and gender using DeepFace."""
    result = DeepFace.analyze(img_path=img_path, actions=['age', 'gender'])
    return [result[0]]
