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
            return redirect(url_for("upload_image"))
        image = request.files["image"]
        if image.filename == "":
            flash("No selected file", "error")
            return redirect(url_for("upload_image"))
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            try:
                image_id = fs.put(image, filename=filename)
                # Immediate check to ensure the image is available in GridFS
                try:
                    fs.get(image_id)  # Verify that the image is retrievable
                except gridfs.errors.NoFile:
                    app.logger.error("Image just saved is not retrievable from GridFS.")
                    flash(
                        "Failed to save image to database, please try again.", "error"
                    )
                    return redirect(url_for("upload_image"))

                images_collection.insert_one(
                    {
                        "image_id": image_id,
                        "filename": filename,
                        "status": "pending",
                        "upload_date": datetime.now(),
                    }
                )
                return redirect(url_for("processing", image_id=str(image_id)))
            except errors.PyMongoError as e:
                app.logger.error("Error saving file to database: %s", e)
                flash("Error saving file to database.", "error")
                return redirect(url_for("upload_image"))
            except Exception as e:
                app.logger.error("Unexpected error: %s", e)
                flash("An unexpected error occurred. Please try again.", "error")
                return redirect(url_for("upload_image"))
        else:
            flash("Invalid file type.", "error")
    # For GET request or any other case where POST conditions aren't met,
    # render the upload form again.
    return render_template("upload.html")


def start_processing(image_id):
    """
    This function would ideally start a background job to process the image
    For simplicity here, we're just calling it directly
    """
    process_image(image_id)


@app.route("/processing/<image_id>")
def processing(image_id):
    return render_template('processing.html', image_id=image_id)

@app.route('/age_data')
def age_data():
    results = list(results_collection.find({}, {"predicted_age": 1, "actual_age": 1}))
    correct_count = 0
    incorrect_count = 0

    for result in results:
        predicted_age = result["predicted_age"]
        actual_age = int(result["actual_age"])  # Ensure actual ages are integers
        if abs(predicted_age - actual_age) <= 1:
            correct_count += 1
        else:
            incorrect_count += 1

    aggregated_data = {
        "correct": correct_count,
        "incorrect": incorrect_count,
    }
    return jsonify(aggregated_data)

@app.route('/age_comparison_data')
def age_comparison_data():
    results = list(results_collection.find({}, {"predicted_age": 1, "actual_age": 1}))
    data = [
        {
            'actual_age': int(result["actual_age"]),
            'predicted_age': result["predicted_age"]
        } for result in results
    ]
    return jsonify(data)


@app.route('/age_distribution')
def age_distribution():
    results = list(results_collection.find({}, {"actual_age": 1}))
    actual_ages = [int(result["actual_age"]) for result in results]
    
    # Define your age bins
    bins = range(0, 101, 10)  # Adjust bins as needed
    bin_labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]
    age_distribution = Counter({label: 0 for label in bin_labels})  # Initialize counter with bins
    
    # Count the ages in each bin
    for age in actual_ages:
        for i in range(len(bins) - 1):
            if bins[i] <= age < bins[i+1]:
                age_distribution[bin_labels[i]] += 1
                break

    return jsonify(dict(age_distribution))

@app.route('/check_status/<image_id>')
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
        image_id = bson.ObjectId(image_id)
    except bson.errors.InvalidId:
        flash('Invalid image ID', 'error')
        return redirect(url_for('home'))

    result = results_collection.find_one({"image_id": image_id}, {'_id': 0})
    if result:
        try:
            fs_image = fs.get(image_id)
            image_data = base64.b64encode(fs_image.read()).decode('utf-8')
        except Exception as e:
            flash('Error retrieving image data', 'error')
            print(f"Error retrieving image data: {e}")
            image_data = None

        predicted_age = result.get('predicted_age')
        actual_age = int(result.get('actual_age', 0))  # Ensure actual_age is an integer
        is_correct = abs(predicted_age - actual_age) <= 1

        # Include the 'image_data' and 'is_correct' in the result dictionary
        result.update({
            'image_data': image_data,
            'is_correct': is_correct
        })

        # Pass the updated 'result' dictionary to the template
        return render_template('results.html', result=result)

    else:
        flash('Result not found.', 'error')
        return redirect(url_for('home'))



if __name__ == '__main__':
    processing_thread = threading.Thread(target=process_images, args=(app,))
    processing_thread.daemon = True
    processing_thread.start()
    app.run(debug=True)
