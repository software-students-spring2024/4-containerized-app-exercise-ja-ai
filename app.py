from pymongo import *
import gridfs

client = MongoClient("mongodb://localhost:27017/")
db = client["faces"]
fs = gridfs.GridFS(db)

# storing small image
with open('./tester_photo.png', 'rb') as image_file:
    fs.put(image_file, filename="tester_photo.jpg")

image = fs.get_last_version(filename="tester_photo.jpg")
with open("./tester_photo2.png", "wb") as f:
    f.write(image.read())
