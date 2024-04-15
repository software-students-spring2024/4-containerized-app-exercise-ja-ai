"""
 API Server
"""

import os
from flask import Flask, request, jsonify
from api import analyze_image


app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Method to communicate between the web-app and the machine learning client
    Returns:
        A JSON of the result
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file:
        path = os.path.join("/tmp", file.filename)
        file.save(path)
        result = analyze_image(path)
        os.remove(path)
        return jsonify(result)
    return jsonify({"error": "Unknown error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
