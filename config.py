import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///staff_management.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Folder paths
    STAFF_IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, 'staff_images')
    STAFF_SIGNATURES_FOLDER = os.path.join(UPLOAD_FOLDER, 'staff_signatures')
    CLEAN_SIGNATURES_FOLDER = os.path.join(UPLOAD_FOLDER, 'staff_signatures_clean')
    
    # Static URL paths for serving files (add these new lines)
    STAFF_IMAGES_URL = '/uploads/staff_images'
    STAFF_SIGNATURES_URL = '/uploads/staff_signatures'
    CLEAN_SIGNATURES_URL = '/uploads/staff_signatures_clean'