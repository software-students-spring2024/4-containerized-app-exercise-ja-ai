FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglib2.0-0

WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install -r requirements.txt

EXPOSE 8000

ENV NAME world

CMD ["python","api.py"]

