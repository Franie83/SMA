# fix_image_paths.py
from app import app, db
from models import Staff
import os
import shutil

with app.app_context():
    staff_members = Staff.query.all()
    
    print("Fixing image paths...")
    
    for staff in staff_members:
        updated = False
        
        # Fix image path
        if staff.image_path:
            # Get just the filename
            filename = os.path.basename(staff.image_path)
            correct_path = f"uploads/staff_images/{filename}"
            
            # Check if file exists at correct location
            if os.path.exists(correct_path):
                if staff.image_path != filename:
                    staff.image_path = filename
                    updated = True
                    print(f"✓ Fixed image path for {staff.full_name}: {filename}")
            else:
                print(f"✗ Missing image for {staff.full_name}: {filename}")
        
        # Fix signature path
        if staff.signature_path:
            filename = os.path.basename(staff.signature_path)
            correct_path = f"uploads/staff_signatures/{filename}"
            
            if os.path.exists(correct_path):
                if staff.signature_path != filename:
                    staff.signature_path = filename
                    updated = True
                    print(f"✓ Fixed signature path for {staff.full_name}: {filename}")
            else:
                print(f"✗ Missing signature for {staff.full_name}: {filename}")
        
        # Fix clean signature path
        if staff.signature_bg_removed_path:
            filename = os.path.basename(staff.signature_bg_removed_path)
            correct_path = f"uploads/staff_signatures_clean/{filename}"
            
            if os.path.exists(correct_path):
                if staff.signature_bg_removed_path != filename:
                    staff.signature_bg_removed_path = filename
                    updated = True
                    print(f"✓ Fixed clean signature path for {staff.full_name}: {filename}")
    
    db.session.commit()
    print("\n✅ Database paths updated!")