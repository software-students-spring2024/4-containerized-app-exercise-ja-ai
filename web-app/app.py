from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import gridfs
from datetime import datetime
import threading
import time
import base64
import tempfile
import sys
import os
import bson
from collections import Counter

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
results_collection.create_index([("image_id", 1), ("upload_date", 1)], unique=True)


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
                    try:
                        results_collection.insert_one({
                            "image_id": image_doc["image_id"],
                            "predicted_age":predicted_age,
                            # "gender":dominant_gender,
                            "actual_age":actual_age,
                            "upload_date": image_doc["upload_date"],
    
                        })
                    except DuplicateKeyError:
                        print("Duplicate entry found, not inserting.")
                    fs.delete(image_doc['image_id'])
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
