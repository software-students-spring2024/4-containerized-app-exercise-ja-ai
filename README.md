![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)

# Containerized App Exercise

# Project Description

Our project utilizes ML to estimate the age of a user. Through our web app, the user can take and upload a photo to be analyzed, then get an estimated age back and see how accurate the program is.

Build a containerized app that uses machine learning. See [instructions](./instructions.md) for details.

# How to run

Make sure you have Docker Desktop installed. If you need to install Docker, you can create an account and download it [here](https://www.docker.com/products/docker-desktop/).

You can create a local repository using the following command

    git clone https://github.com/software-students-spring2024/4-containerized-app-exercise-ja-ai.git

The navigate into your local repository. Then run the following command. This will remove any containers whose ports are needed.

    docker-compose down

To install the required dependencies and run the program, run the following command. It may take some time to download all of the necessary dependencies the first time. Once you've installed the required dependencies once, you can run the command without the --build tag.

    docker-compose up --build

To open the app, open a web browser and navigate to [localhost:5002](http://localhost:5002/). Do not go to the address that the program tells you to navigate to.

Please Note that the first time you upload a picture, it will take a while to process. This is because the program is downloading the necessary files to run the machine learning model. Subsequent uploads will be faster.

# Starter Data

No starter data is required.

# Contributors

- [Adam Schwartz](https://github.com/aschwartz01)
- [Alex Kondratiuk](https://github.com/ak8000)
- [Janet Pan](https://github.com/jp6024)
- [Isaac Kwon](https://github.com/iok206)
