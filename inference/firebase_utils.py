import firebase_admin
from firebase_admin import credentials, storage
from google.cloud import storage as gcs

# Initialize the app with a service account, granting admin privileges
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'theshow-587b1.firebasestorage.app'
})
bucket = storage.bucket()

def upload_web_data(local_path: str, remote_name: str = 'web_data.csv'):
    blob = bucket.blob(remote_name)
    blob.upload_from_filename(local_path, content_type='text/csv')
    print(f"Uploaded {local_path} as {remote_name}")