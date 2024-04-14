"""
Flask App for uploading and processing images.
"""

import base64
import os
import tempfile

# import threading
# import time
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
app.secret_key = os.getenv("SECRET_KEY")

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


@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    """
    Function to upload the image to be processed

    Returns:
        The processing.html page
    """
    if request.method == "POST":
        if "image" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        image = request.files["image"]
        if image.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)
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
                    }
                )
                start_processing(str(image_id))
                return redirect(url_for("processing", image_id=str(image_id)))
            except errors.PyMongoError as e:
                app.logger.error("Error saving file to database: %s", e)
                flash("Error saving file to database.", "error")
            # except Exception as e:
            #     app.logger.error("An unexpected error occurred: %s", e)
            #     traceback.print_exc()
            #     flash("An unexpected error occurred while uploading the file.", "error")
        flash("Invalid file type.", "error")
        # Redirect to home only if it's a POST request and something goes wrong
        return redirect(url_for("home"))
    # Render the upload form template for GET request
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
    app.logger.info("Starting image processing for image ID: %s", image_id)

    # Check if the image has already been processed or is being processed
    image_doc = images_collection.find_one({"_id": bson.ObjectId(image_id)})
    if not image_doc:
        app.logger.error("No image found for image ID: %s", image_id)
        return
    if image_doc["status"] != "pending":
        app.logger.error(
            "Image is not pending, current status is: %s", image_doc["status"]
        )
        return
    # Proceed with processing
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
                    "http://machine_learning_client:5001/analyze",
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
            {"_id": image_doc["_id"]}, {"$set": {"status": "processed"}}
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
    except gridfs.errors.NoFile as e:
        app.logger.error("GridFS file not found: %s", e)
    except errors.PyMongoError as e:
        app.logger.error("MongoDB operation failed: %s", e)
    except requests.exceptions.RequestException as e:
        app.logger.error("Request failed: %s", e)
    except OSError as e:
        app.logger.error("OS error during file handling: %s", e)
    finally:
        app.logger.error("Error processing image %s: %s", image_id, e)
        traceback.print_exc()
        # Set status to "failed" to indicate processing did not complete
        images_collection.update_one(
            {"_id": bson.ObjectId(image_id)}, {"$set": {"status": "failed"}}
        )
        app.logger.info("Image status updated to 'failed' for image ID: %s", image_id)


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
