"""
Flask App for uploading and processing images.
"""

# import base64
import os
import queue
import tempfile
import threading
import time
# import traceback
from datetime import datetime
from dotenv import load_dotenv
from flask import flash, Flask, jsonify, render_template, request, redirect, url_for
import bson
import gridfs
# from requests.exceptions import RequestException

# import werkzeug
from werkzeug.utils import secure_filename
from pymongo import MongoClient
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


@app.route("/processing/<image_id>")
def processing(image_id):
    """
    Instead of threading, let's call process_image directly.
    """

    grid_out = fs.get(bson.ObjectId(image_id))
    _, temp_filepath = tempfile.mkstemp()
    with open(temp_filepath, "wb") as f:
        f.write(grid_out.read())
    with open(temp_filepath, "rb") as file:
        requests.post(
            "http://machine-learning-client:5001/analyze",
            files={"file": file},
            data={"image_id": str(image_id)},
            timeout=1000,
        )

    wait_interval = 5

    while True:
        current_image_doc = images_collection.find_one(
            {"image_id": bson.ObjectId(image_id)}
        )
        if current_image_doc and current_image_doc.get("status") == "success":
            return redirect(url_for("show_results", image_id=image_id))
        if current_image_doc and current_image_doc.get("status") == "failed":
            # call a method that prints an error message to the screen/ add exception
            print("no")

        time.sleep(wait_interval)
    app.logger.error("Something went wrong")
    # call a method that prints an error message to the screen


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
        if "image" not in request.files or "age" not in request.form:
            flash("Missing data", "error")
            return jsonify({"error": "Missing data"}), 400
        image = request.files["image"]
        actual_age = request.form["age"]
        if image.filename == "":
            flash("No selected file", "error")
            return jsonify({"error": "No selected file"}), 400
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            try:
                image_id = fs.put(image, filename=filename)
                images_collection.insert_one(
                    {
                        "image_id": image_id,
                        "filename": filename,
                        "status": "pending",
                        "upload_date": datetime.now(),
                        "actual_age": str(actual_age),
                    }
                )
                return (
                    jsonify(
                        {
                            "message": "File uploaded successfully",
                            "task_id": str(image_id),
                        }
                    ),
                    200,
                )
            except FileNotFoundError as e:
                app.logger.error("File upload failed: %s", str(e))
                return jsonify({"error": "File not found"}), 500
        else:
            return jsonify({"error": "Invalid file type"}), 400
    return render_template("upload.html")


@app.route("/results/<image_id>")
def show_results(image_id):
    """
    Function that brings you to the results.html after the image is done processing

    Returns:
        result.html
    """
    # Convert the image_id to a BSON ObjectId
    obj_id = bson.ObjectId(image_id)
    specific_result = results_collection.find_one({"image_id": obj_id})
    print(specific_result)
    if not specific_result:
        flash("Result not found.", "error")
        return redirect(url_for("home"))

    # Fetch all results for the graph
    all_results = results_collection.find({})
    predicted_ages = []
    actual_ages = []
    labels = []
    index = 0
    for result in all_results:
        if 'actual_age' in result and 'predicted_age' in result:
            actual_ages.append(result['actual_age'])
            predicted_ages.append(result['predicted_age'])
            labels.append(str(index))  # Use the index or any specific identifier
            index += 1

    return render_template("results.html", specific_result=specific_result, predicted_ages=predicted_ages, actual_ages=actual_ages, labels=labels)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
