# Use Python 3.11 as the base image
FROM  python:3.11.0

LABEL maintainer="kilian.lehn"

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app directory contents into the container
COPY app /app

# Set the environment variable for the service account key
ENV CLOUD_STORAGE_BUCKET= '****'
# Mount the local service account key file as a Docker secret
RUN mkdir /run/secrets
COPY **** /run/secrets/****
RUN chmod 400 /run/secrets/****

# Expose the port that Flask will run on
EXPOSE 5000
ENV PORT 5000


CMD exec gunicorn --bind :$PORT app:app