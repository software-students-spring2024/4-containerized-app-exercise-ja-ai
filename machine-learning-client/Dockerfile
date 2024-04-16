FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    libgl1-mesa-dev \
    libglib2.0-0 \
    pkg-config \
    libhdf5-dev \
    gcc

WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install --retries=5 --default-timeout=300 opencv-python
RUN pip install --retries=3 --default-timeout=150 -r requirements.txt


EXPOSE 5001

CMD ["python", "api_server.py"]