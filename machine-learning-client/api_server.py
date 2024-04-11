from flask import Flask, request, jsonify
from api import analyze_image
import os

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        path = os.path.join('/tmp', file.filename)
        file.save(path)
        result = analyze_image(path)
        os.remove(path)
        return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
