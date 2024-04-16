"""
 API Server
"""

import os
from flask import Flask, request, jsonify
from pymongo import MongoClient
import gridfs
import bson
from api import analyze_image

app = Flask(__name__)

serverOptions = {
    "socketTimeoutMS": 600000,  # 10 minutes
    "connectTimeoutMS": 30000,  # 30 seconds
    "serverSelectionTimeoutMS": 30000,  # 30 seconds
}

client = MongoClient("mongodb://mongodb:27017/", **serverOptions)
db = client["faces"]
fs = gridfs.GridFS(db)

images_collection = db["images_pending_processing"]
results_collection = db["image_processing_results"]


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Method to communicate between the web-app and the machine learning client
    Returns:
        A JSON of the result
    """
    image_id = request.form.get("image_id")
    if "file" not in request.files:
        images_collection.update_one(
            {"image_id":bson.ObjectId(image_id)},
            {"$set": {"status": "failed"}},
        )
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        images_collection.update_one(
            {"image_id":bson.ObjectId(image_id)},
            {"$set": {"status": "failed"}},
        )
        return jsonify({"error": "No selected file"}), 400
    if file:
        path = os.path.join("/tmp", file.filename)
        file.save(path)
        result = analyze_image(path)
        os.remove(path)
        images_collection.update_one(
            {"image_id":bson.ObjectId(image_id)},
            {"$set": {"status": "success"}},
        )
        results_collection.insert_one(
            {
                "image_id": bson.ObjectId(image_id),
                "predicted_age": result,
            }
        )
        return jsonify(result)
    images_collection.update_one(
            {"image_id": bson.ObjectId(image_id)},
            {"$set": {"status": "failed"}},
    )
    return jsonify({"error": "Unknown error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
