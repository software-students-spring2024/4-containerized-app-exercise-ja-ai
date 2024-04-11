"""
Flask App
"""

import base64
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for
import bson
import gridfs
from werkzeug.utils import secure_filename
from pymongo import MongoClient, errors
import cv2
import datetime

MACHINE_LEARNING_CLIENT_PATH = os.path.abspath('../machine-learning-client')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

sys.path.insert(0, MACHINE_LEARNING_CLIENT_PATH)

from api import analyze_image

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["faces"]
fs = gridfs.GridFS(db)

images_collection = db["images_pending_processing"]
results_collection = db["image_processing_results"]
results_collection.create_index([("image_id", 1), ("upload_date", 1)], unique=True)

# Image Capture
camera = cv2.VideoCapture(0)
capture_frame = None
now = datetime.datetime.now()

def gen_frames():
    global capture_frame
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Convert the frame to JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            # Store the frame for capturing
            capture_frame = frame  
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# checking directory exists, else makes new one
def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

@app.route('/capture', methods=['POST'])
def capture():
    global capture_frame
    if request.method == 'POST':
        if capture_frame is not None:
            now = datetime.datetime.now()
            filename = f"captured_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
            shots_directory = './shots'
            # creating shots directory (to save photos)
            ensure_directory(shots_directory)  
            filepath = os.path.join(shots_directory, filename) 
            cv2.imwrite(filepath, capture_frame)  
            # this returns to the index page (where user can upload photo)
            return redirect(url_for('index'))  
    return 'Error: Image capture failed.'

# End Camera Capture

def allowed_file(filename):
    """
    Checks if the uploaded file's extension is allowed
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_images(flask_app):
    """
    Continously check for and process pending images in the MongoDB
    Each image is analyzed, and the results are updated in the database

    Args:
        app (Flask): The Flask application object for context
    """
    with flask_app.app_context():
        while True:
            image_doc = images_collection.find_one({"status": "pending"})
            if image_doc:
                try:
                    grid_out = fs.get(image_doc['image_id'])
                    _, temp_filepath = tempfile.mkstemp()
                    with open(temp_filepath, 'wb') as f:
                        f.write(grid_out.read())

                    result = analyze_image(temp_filepath)
                    os.remove(temp_filepath)

                    # Update the database with analysis results
                    images_collection.update_one(
                        {"_id": image_doc["_id"]},
                        {"$set": {"status": "processed"}}
                    )
                    predicted_age = result[0]['age']
                    # gender_scores = result[0]['gender']
                    # # dominant_gender = "Man"
                    # # if gender_scores["Man"] < gender_scores['Woman']:
                    # #     dominant_gender = "Woman"
                    actual_age = image_doc.get("actual_age")
                    try:
                        results_collection.insert_one({
                            "image_id": image_doc["image_id"],
                            "predicted_age":predicted_age,
                            # "gender":dominant_gender,
                            "actual_age":actual_age,
                            "upload_date": image_doc["upload_date"],
                        })
                    except errors.DuplicateKeyError:
                        print("Duplicate entry found, not inserting.")
                    fs.delete(image_doc['image_id'])
                    print(
                        f"Processed and removed image: {image_doc['filename']} "
                        f"with results: {result}"
                    )
                except Exception as e:
                    print(f"Error processing image {image_doc['filename']}: {e}")
            else:
                print("No images to process.")
            time.sleep(5)

@app.route('/', methods=['GET'])
def home():
    """
    Brings to the homepage of the app
    """
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_image():
    """
    Upload endpoint for submitting images
    Stores images in MongoDB and marks them as pending for processing

    Returns:
        Response: Redirects to processing page or re-renders upload form with error message
    """
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        image = request.files['image']
        if image.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_id = fs.put(image, filename=filename)
            actual_age = request.form.get("actual_age")
            images_collection.insert_one({
                'image_id': image_id,
                'filename': filename,
                'status': 'pending',
                'upload_date': datetime.now(),
                "actual_age":actual_age,
            })
            # flash('Image successfully uploaded and awaiting processing.', 'success')
            return redirect(url_for('processing', image_id=str(image_id)))
    return render_template('upload.html')

@app.route('/processing/<image_id>')
def processing(image_id):
    """
    Brings you to the processing page

    Returns:
         Response: Redirects to processing page 
    """
    return render_template('processing.html', image_id=image_id)

@app.route('/age_comparison_data')
def age_comparison_data():
    """
    Processes the data for the graph

    Returns:
        JSON of the data for the graph
    """
    results = list(results_collection.find({}, {"predicted_age": 1, "actual_age": 1}))
    data = [
        {
            'actual_age': int(result["actual_age"]),
            'predicted_age': result["predicted_age"]
        } for result in results
    ]
    return jsonify(data)

@app.route('/check_status/<image_id>')
def check_status(image_id):
    """
    Checks the status of the process

    Returns:
        JSON of the result
    """
    try:
        image_id = bson.ObjectId(image_id)
    except bson.errors.InvalidId:
        return jsonify({'status': 'error', 'message': 'Invalid image ID'}), 400
    image_doc = images_collection.find_one({'image_id': image_id})
    if image_doc and image_doc['status'] == 'processed':
        images_collection.delete_one({"_id": image_doc['_id']})
        return jsonify({'status': 'processed', 'image_id': str(image_id)})
    return jsonify({'status': 'pending'})

@app.route('/results/<image_id>')
def show_results(image_id):
    """
    Calls the results.html page

    Returns:
        Redirects: Redirects you to the results page if everything worked 
                    correctly, or to the homepage if there were errors
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
            # flash('Error retrieving image data', 'error')
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
    flash('Result not found.', 'error')
    return redirect(url_for('home'))



if __name__ == '__main__':
    processing_thread = threading.Thread(target=process_images, args=(app,))
    processing_thread.daemon = True
    processing_thread.start()
    app.run(debug=True)
