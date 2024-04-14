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
    """
    Instead of threading, let's call process_image directly.
    """
    try:
        process_image(image_id)
        return redirect(url_for("show_results", image_id=image_id))
    except errors.PyMongoError as e:
        app.logger.error("Database error during image processing: %s", e)
        flash("A database error occurred while processing the image.", "error")
    except requests.exceptions.RequestException as e:
        app.logger.error("HTTP request error during image processing: %s", e)
        flash("A network error occurred while processing the image.", "error")
    except OSError as e:
        app.logger.error("File handling error during image processing: %s", e)
        flash("A file handling error occurred while processing the image.", "error")
    # except Exception as e:
    #     app.logger.error("An unexpected error occurred during image processing: %s", e)
    #     flash("An unexpected error occurred while processing the image.", "error")
    return redirect(url_for("home"))


def process_image(image_id):
    """
    Function that processes the images for upload

    Returns:
        Nothing. Prints if the image was processed successfully
    """
    retry_attempts = 5
    retry_interval = 5  # seconds

    for attempt in range(retry_attempts):
        app.logger.info("Attempt %d to process image ID: %s", (attempt + 1), image_id)
        try:
            # Attempt to retrieve the image file from GridFS
            grid_out = fs.get(bson.ObjectId(image_id))
        except gridfs.errors.NoFile:
            app.logger.warning("Image not found in GridFS, retrying...")
            time.sleep(retry_interval)
            continue
        image_doc = images_collection.find_one({"image_id": bson.ObjectId(image_id)})
        if image_doc and image_doc["status"] == "pending":
            # Proceed with processing if image_doc is valid
            try:
                # Retrieve the image file from GridFS
                grid_out = fs.get(image_doc["image_id"])
                _, temp_filepath = tempfile.mkstemp()
                with open(temp_filepath, "wb") as f:
                    f.write(grid_out.read())
                app.logger.info("Image written to temporary file: %s", temp_filepath)

                # Call the ML model for processing
                try:
                    with open(temp_filepath, "rb") as file:
                        response = requests.post(
                            "http://machine-learning-client:5001/analyze",
                            files={"file": file},
                            timeout=10,
                        )
                    result = response.json()
                    app.logger.info("Received analysis result: %s", result)
                finally:
                    os.remove(temp_filepath)
                    app.logger.info("Temporary file removed: %s", temp_filepath)

                # Update the database with the analysis results
                update_result = images_collection.update_one(
                    {"_id": image_doc["_id"]}, 
                    {"$set": {"status": "processed", "analysis": result}}
                )
                app.logger.info(
                    "Image status updated in images_collection. Modified count: %s",
                    update_result.modified_count,
                )

                # Insert the result into the results_collection
                insert_result = results_collection.insert_one(
                    {
                        "image_id": image_doc["image_id"],
                        "filename": image_doc["filename"],
                        "analysis": result,
                        "upload_date": image_doc["upload_date"],
                    }
                )
                app.logger.info(
                    "Result inserted into results_collection with ID: %s",
                    insert_result.inserted_id,
                )
                return
            except errors.PyMongoError as e:
                app.logger.error("MongoDB operation failed: %s", e)
                # handle MongoDB specific logic here
            except Exception as e:
                app.logger.error("Unexpected error occurred: %s", e)
                traceback.print_exc()
            finally:
                # Set status to "failed" to indicate processing did not complete
                images_collection.update_one(
                    {"_id": bson.ObjectId(image_id)}, {"$set": {"status": "failed"}}
                )
                app.logger.info(
                    "Image status updated to 'failed' for image ID: %s", image_id
                )
        if attempt < retry_attempts - 1:
            time.sleep(retry_interval)
    # got rid of else for pylinting. If necessary, add it back in
    app.logger.error(
        "No image found for image ID: %s after %s attempts.",
        image_id, 
        retry_attempts,
    )


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
        image_id = bson.ObjectId(image_id)
    except bson.errors.InvalidId:
        flash("Invalid image ID.", "error")
        return redirect(url_for("home"))
    result = results_collection.find_one({"image_id": image_id}, {"_id": 0})
    if result:
        try:
            fs_image = fs.get(image_id)
            result["image_data"] = base64.b64encode(fs_image.read()).decode("utf-8")
            # Assuming `result["analysis"]` contains "age" and "gender"
            result.update(result["analysis"])
        except gridfs.errors.NoFile:
            flash("File not found in database.", "error")
            return redirect(url_for("home"))
        except KeyError as e:
            flash(f"Key error in result analysis: {str(e)}", "error")
            return redirect(url_for("home"))
        except gridfs.errors.GridFSError as e:
            flash(f"Error accessing file in GridFS: {str(e)}", "error")
            return redirect(url_for("home"))
        return render_template(
            "results.html", result=result, filename=result["filename"]
        )
    flash("Result not found.", "error")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
