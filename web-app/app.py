from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
import bson

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
                    gender_scores = result[0]['gender']
                    dominant_gender = "Man" if gender_scores["Man"] > gender_scores['Woman'] else "Woman"
                    actual_age = image_doc.get("actual_age")

                    results_collection.insert_one({
                        "image_id": image_doc["image_id"],
                        "predicted_age":predicted_age,
                        "gender":dominant_gender,
                        "actual_age":actual_age,
                        
                        # "filename": image_doc["filename"],
                        # "analysis": result,  # Save the analysis results in the database
                        # "upload_date": image_doc["upload_date"]
                    })
                    fs.delete(image_doc['image_id'])
                    # images_collection.delete_one({"_id": image_doc['_id']})
                    print(f"Processed and removed image: {image_doc['filename']} with results: {result}")

                except Exception as e:
                    print(f"Error processing image {image_doc['filename']}: {e}")
            else:
                print("No images to process.")
            time.sleep(5)


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
    return render_template('processing.html', image_id=image_id)

@app.route('/check_status/<image_id>')
def check_status(image_id):
    try:
        image_id = bson.ObjectId(image_id)
    except bson.errors.InvalidId:
        return jsonify({'status': 'error', 'message': 'Invalid image ID'}), 400
    image_doc = images_collection.find_one({'image_id': image_id})
    if image_doc and image_doc['status'] == 'processed':
        images_collection.delete_one({"_id": image_doc['_id']})
        return jsonify({'status': 'processed', 'image_id': str(image_id)})
    else:
        return jsonify({'status': 'pending'})

@app.route('/results/<image_id>')
def show_results(image_id):
    try:
        image_id = bson.ObjectId(image_id)
    except bson.errors.InvalidId:
        return "Invalid image ID", 400
    result = results_collection.find_one({"image_id": image_id}, {'_id': 0})
    if result:
        try:
            fs_image = fs.get(image_id)
            result['image_data'] = base64.b64encode(fs_image.read()).decode('utf-8')
        except:
            result['image_data'] = None
        return render_template('results.html', results=[result])
    else:
        flash('Result not found.', 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    processing_thread = threading.Thread(target=process_images, args=(app,))
    processing_thread.daemon = True
    processing_thread.start()
    app.run(debug=True)
