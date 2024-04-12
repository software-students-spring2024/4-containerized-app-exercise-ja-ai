FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglib2.0-0

WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

EXPOSE 5000

ENV FLASK_APP app.py
ENV FLASK_RUN_HOST 0.0.0.0

CMD ["flask", "run"]