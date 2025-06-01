# Use an official Python runtime as a parent image
FROM python:3.10

# Set a working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your Flask app
COPY . .

# Make sure the Flask app listens on $PORT
ENV PORT 8080
ENV PYTHONUNBUFFERED True

# If you rely on FIREBASE_SA (base64) like on Heroku, decode it here:
# (Optional—see note below)
# RUN pip install --no-cache-dir firebase-admin

# Expose port 8080
EXPOSE 8080

# Start the Gunicorn server
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080"]
