from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import hashlib

db = SQLAlchemy()

class Staff(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    ministry = db.Column(db.String(200), default='Ministry of Communication')
    department = db.Column(db.String(200))
    designation = db.Column(db.String(200))
    image_path = db.Column(db.String(500))
    signature_path = db.Column(db.String(500))
    signature_bg_removed_path = db.Column(db.String(500))
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(200))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    
    def set_password(self, password):
        self.password = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password == hashlib.sha256(password.encode()).hexdigest()
    
    def get_id(self):
        return str(self.id)

class Admin(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='admin')
    
    def set_password(self, password):
        self.password = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password == hashlib.sha256(password.encode()).hexdigest()
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def get_id(self):
        return str(self.id)

class ImportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    records_imported = db.Column(db.Integer)
    records_failed = db.Column(db.Integer)
    import_date = db.Column(db.DateTime, default=datetime.utcnow)
    imported_by = db.Column(db.String(100))
    error_log = db.Column(db.Text)