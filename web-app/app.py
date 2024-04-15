"""
Flask App for uploading and processing images.
"""

import base64
import os
import queue
import tempfile
import threading
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
from flask import flash, Flask, jsonify, render_template, request, redirect, url_for
import bson
import gridfs
from requests.exceptions import RequestException

# import werkzeug
from werkzeug.utils import secure_filename
from pymongo import MongoClient, errors
import requests


load_dotenv()

app = Flask(__name__)
task_queue = queue.Queue()
results = {}


# MongoDB connection
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

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    """
    Function that makes sure the uploaded picture file is in the allowed extensions

    Returns:
        A boolean
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def home():
    """
    Creates the template for the homepage
    """
    return render_template("index.html")


def process_task():
    """
    Function to process the tasks
    """
    while True:
        task_id = task_queue.get()  # Wait until a task is available
        print(f"Processing task {task_id}")
        time.sleep(10)  # Simulate a long-running task
        results[task_id] = "Task Completed"
        task_queue.task_done()


# Start a background thread to process tasks
threading.Thread(target=process_task, daemon=True).start()


@app.route("/start_task", methods=["POST"])
def start_task():
    """
    Function to start the tasks
    """
    task_id = request.json.get("task_id")
    task_queue.put(task_id)
    return jsonify({"message": "Task started", "task_id": task_id}), 202


@app.route("/get_result/<task_id>", methods=["GET"])
def get_result(task_id):
    """
    Gets the result
    """
    result = results.get(task_id)
    if result:
        return jsonify({"task_id": task_id, "status": result})
    return jsonify({"task_id": task_id, "status": "Processing"}), 202


app.secret_key = os.getenv("SECRET_KEY")


@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    """
    Function to upload the image to be processed and ensure its availability in GridFS
    before starting processing. It handles file uploads and redirects to processing or
    reloads the upload form with error messages based on upload success.

    Returns:
        Redirect to the image processing page if upload is successful,
        or re-render the upload page with appropriate error messages if not.
    """
    if request.method == "POST":
        if "image" not in request.files:
            flash("No file part", "error")
            return jsonify({"error": "No file part"}), 400
        image = request.files["image"]
        if image.filename == "":
            flash("No selected file", "error")
            return jsonify({"error": "No selected file"}), 400
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            try:
                image_id = fs.put(image, filename=filename)
                images_collection.insert_one({
                    "image_id": image_id,
                    "filename": filename,
                    "status": "pending",
                    "upload_date": datetime.now(),
                })
                return jsonify({"message": "File uploaded successfully", "task_id": str(image_id)}), 200
            except Exception as e:
                app.logger.error("Upload failed: %s", str(e))
                return jsonify({"error": "Failed to upload image"}), 500
        else:
            return jsonify({"error": "Invalid file type"}), 400
    return render_template("upload.html")

def start_processing(image_id):
    """
    This function would ideally start a background job to process the image
    For simplicity here, we're just calling it directly
    """
    process_image(image_id)

@app.route("/processing/<image_id>")
def processing(image_id):
    """
    Instead of threading, let's call process_image directly.
    """
    try:
        process_image(image_id)
        return redirect(url_for("show_results", image_id=image_id))
    except ValueError as ve:
        app.logger.error("Processing error: %s", str(ve))
        flash("Error processing image. " + str(ve), "error")
        return redirect(url_for("home")), 500
    except Exception as e:
        app.logger.error("Unexpected error: %s", str(e))
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("home")), 500


def process_image(image_id):
    """
    Function that processes the images for upload.

    Args:
        image_id (str): The MongoDB document ID of the image to be processed.
    """
    grid_out = fs.get(bson.ObjectId(image_id))
    _, temp_filepath = tempfile.mkstemp()
    with open(temp_filepath, "wb") as f:
        f.write(grid_out.read())
    with open(temp_filepath, "rb") as file:
        response = requests.post(
            "http://machine-learning-client:5001/analyze",
            files={"file": file},
            timeout=600,
        )
    result = response.json()
    app.logger.info(f"Data received from ML model: {result}")
    validated_result = validate_and_transform_ml_data(result)
    if validated_result is None:
        raise ValueError("Invalid data received from ML model")
    update_analysis_result(image_id, validated_result)
    return "Success"

def validate_and_transform_ml_data(data):
    """
    Ensures the ML model's output matches the expected format.
    Args:
        data (list): The raw data list from the ML model.
    Returns:
        list: Transformed data if valid, None if invalid.
    """
    if not isinstance(data, list):
        app.logger.error("Invalid ML data format: Not a list")
        return None
    for entry in data:
        if not isinstance(entry, dict) or 'age' not in entry:
            app.logger.error(f"Invalid ML data format: Entry issue {entry}")
            return None
    transformed_data = [{'age': entry['age']} for entry in data]
    return transformed_data



def update_analysis_result(image_doc, ages):
    # Update the database with the age results
    update_result = images_collection.update_one(
        {"_id": image_doc["_id"]},
        {"$set": {"status": "processed", "analysis": {"ages": ages}}}
    )
    app.logger.info(f"Image status updated in images_collection. Modified count: {update_result.modified_count}")

    # Insert the result into the results_collection if needed
    results_collection.insert_one({
        "image_id": image_doc["image_id"],
        "filename": image_doc["filename"],
        "analysis": {"ages": ages},
        "upload_date": image_doc["upload_date"],
    })
    app.logger.info("Result inserted into results_collection.")


def process_result(image_doc, result):
    """
    Update database and handle the correct result format.

    Args:
        image_doc (dict): The document of the image being processed.
        result (list): The result of the image processing to be stored.
    """
    update_result = images_collection.update_one(
        {"_id": image_doc["_id"]},
        {"$set": {"status": "processed", "analysis": result}}
    )
    app.logger.info("DB update success, modified count: %s", update_result.modified_count)
    results_collection.insert_one({
        "image_id": image_doc["image_id"],
        "filename": image_doc["filename"],
        "analysis": result,
        "upload_date": image_doc["upload_date"],
    })


def task_cleanup(image_id, status="failed"):
    """
    Cleanup or update task status in the database.

    Args:
        image_id (str): The MongoDB document ID of the image.
        status (str): The status to be set for the task.
    """
    images_collection.update_one(
        {"_id": bson.ObjectId(image_id)},
        {"$set": {"status": status}}
    )
    app.logger.info(f"Image status updated to '{status}' for image ID: {image_id}")



@app.route("/check_status/<image_id>")
def check_status(image_id):
    """
    Function that checks the status of the images being processed

    Returns:
        A JSON of the result
    """
    image_doc = images_collection.find_one({"_id": bson.ObjectId(image_id)})
    if image_doc and image_doc["status"] == "processed":
        return jsonify({"status": "processed", "image_id": str(image_id)})
    if image_doc and image_doc["status"] == "failed":
        return jsonify({"status": "failed"})
    return jsonify({"status": "pending"})


@app.route("/results/<image_id>")
def show_results(image_id):
    """
    Function that brings you to the results.html after the image is done processing

    Returns:
        result.html
    """
    try:
        # Convert the image_id to a BSON ObjectId
        obj_id = bson.ObjectId(image_id)
        result = results_collection.find_one({"image_id": obj_id}, {"_id": 0})
        if not result:
            flash("Result not found.", "error")
            return redirect(url_for("home"))

        # Retrieve and encode the image data
        try:
            fs_image = fs.get(obj_id)
            result["image_data"] = base64.b64encode(fs_image.read()).decode("utf-8")
        except Exception as e:
            app.logger.error("Failed to retrieve or encode image data: %s", e)
            flash("Failed to retrieve image data.", "error")
            return redirect(url_for("home"))

        # Ensure the analysis results are in the expected format (list of dictionaries)
        if "analysis" in result:
            if isinstance(result["analysis"], list) and all(isinstance(face, dict) for face in result["analysis"]):
                faces_data = [{
                    "age": face.get("age"),
                    "gender": face.get("dominant_gender"),
                    "confidence": face.get("face_confidence")
                } for face in result["analysis"]]
                result["faces_data"] = faces_data
            else:
                app.logger.error("Analysis results are not in the expected format: %s", result["analysis"])
                flash("Analysis results are incomplete or in an unexpected format.", "error")
                return redirect(url_for("home"))
        else:
            app.logger.error("No analysis results found in the document.")
            flash("No analysis results found.", "error")
            return redirect(url_for("home"))

        # Render the results page with the processed data
        return render_template("results.html", result=result)
    except bson.errors.InvalidId:
        app.logger.error("Invalid ObjectId: %s", image_id)
        flash("Invalid image ID.", "error")
        return redirect(url_for("home"))
    except Exception as e:
        app.logger.error(f"Error processing results: {e}")
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
