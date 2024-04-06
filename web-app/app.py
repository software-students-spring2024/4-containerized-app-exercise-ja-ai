# app.py
import base64

from flask import Flask, render_template
from pymongo import MongoClient
import gridfs

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["faces"]
fs = gridfs.GridFS(db)

@app.route('/')
def home():
    # retrieve stored image
    image = fs.get_last_version(filename="tester_photo.jpg")
    
    # base64-encode the image data
    encoded_image = base64.b64encode(image.read()).decode('utf-8')

    # fetch results
    ml_results = list(db.results.find())

    # pass results to html template
    return render_template('index.html', encoded_image=encoded_image, ml_results=ml_results)

if __name__ == '__main__':
    app.run(debug=True)
