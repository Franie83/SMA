# fix_paths_final.py
from app import app, db
from models import Staff
import os

with app.app_context():
    staff_members = Staff.query.all()
    
    for staff in staff_members:
        updated = False
        
        # Fix image path
        if staff.image_path:
            # Replace backslashes with forward slashes and get just filename
            clean_path = staff.image_path.replace('\\', '/')
            filename = os.path.basename(clean_path)
            if staff.image_path != filename:
                staff.image_path = filename
                updated = True
                print(f"Fixed image path for {staff.full_name}: {filename}")
        
        # Fix signature path
        if staff.signature_path:
            clean_path = staff.signature_path.replace('\\', '/')
            filename = os.path.basename(clean_path)
            if staff.signature_path != filename:
                staff.signature_path = filename
                updated = True
                print(f"Fixed signature path for {staff.full_name}: {filename}")
        
        # Fix clean signature path
        if staff.signature_bg_removed_path:
            clean_path = staff.signature_bg_removed_path.replace('\\', '/')
            filename = os.path.basename(clean_path)
            if staff.signature_bg_removed_path != filename:
                staff.signature_bg_removed_path = filename
                updated = True
                print(f"Fixed clean signature path for {staff.full_name}: {filename}")
    
    db.session.commit()
    print("\n✅ All paths fixed!")