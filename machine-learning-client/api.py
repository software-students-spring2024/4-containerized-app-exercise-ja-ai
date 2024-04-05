from deepface import DeepFace

print("Hello world")
result = DeepFace.analyze(img_path = "tester_photo2.png", 
                          actions=['age','gender'])

print("Age: ", result[0]['age'])
# print("Gender: ", result[0]['dominant_gender'])

# print(result)