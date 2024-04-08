from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import gridfs
from datetime import datetime
import threading
import time
import base64
import tempfile
import sys
import os

machine_learning_client_path = os.path.abspath('../machine-learning-client')
sys.path.insert(0, machine_learning_client_path)

from api import analyze_image

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["faces"]
fs = gridfs.GridFS(db)

images_collection = db["images_pending_processing"]
results_collection = db["image_processing_results"]

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_images(app):
    with app.app_context():
        while True:
            image_doc = images_collection.find_one({"status": "pending"})
            if image_doc:
                # Retrieve image from GridFS
                try:
                    grid_out = fs.get(image_doc['image_id'])
                    _, temp_filepath = tempfile.mkstemp()
                    with open(temp_filepath, 'wb') as f:
                        f.write(grid_out.read())

                    # Process image using DeepFace
                    result = analyze_image(temp_filepath)
                    os.remove(temp_filepath)  # Clean up the temporary file

                    # Update the database with analysis results
                    images_collection.update_one(
                        {"_id": image_doc["_id"]},
                        {"$set": {"status": "processed"}}
                    )
                    results_collection.insert_one({
                        "image_id": image_doc["image_id"],
                        "filename": image_doc["filename"],
                        "analysis": result,
                        "upload_date": image_doc["upload_date"]
                    })
                    print(f"Processed image: {image_doc['filename']} with results: {result}")
                except Exception as e:
                    print(f"Error processing image {image_doc['filename']}: {e}")

            else:
                print("No images to process.")
            time.sleep(5)  # Check for new images every 5 seconds


@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_image():
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
            actual_age = request.form.get('actual_age', None)  # Get 'actual_age' from the form
            images_collection.insert_one({
                'image_id': image_id,
                'filename': filename,
                'status': 'pending',
                'upload_date': datetime.now(),
                'actual_age': actual_age  # Include 'actual_age' in the document
            })
            flash('Image successfully uploaded and awaiting processing.', 'success')
            return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/results')
def show_results():
    results = list(results_collection.find({}, {'_id': 0}))
    for result in results:
        try:
            fs_image = fs.get(result['image_id'])
            result['image_data'] = base64.b64encode(fs_image.read()).decode('utf-8')
        except:
            result['image_data'] = None
    return render_template('results.html', results=results)

if __name__ == '__main__':
    processing_thread = threading.Thread(target=process_images, args=(app,))
    processing_thread.start()
    app.run(debug=True)