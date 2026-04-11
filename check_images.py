# check_images.py
from app import app, db
from models import Staff
import os

with app.app_context():
    staff_members = Staff.query.all()
    
    print("\n=== IMAGE PATH CHECK ===\n")
    
    for staff in staff_members:
        print(f"Staff: {staff.full_name}")
        print(f"  Image path in DB: {staff.image_path}")
        print(f"  Signature path in DB: {staff.signature_path}")
        
        # Check if files exist
        if staff.image_path:
            # Try different possible locations
            possible_paths = [
                staff.image_path,
                os.path.join('uploads', 'staff_images', os.path.basename(staff.image_path)),
                os.path.join('uploads/staff_images', os.path.basename(staff.image_path)),
                f"uploads/staff_images/{os.path.basename(staff.image_path)}"
            ]
            
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    print(f"  ✓ Image found at: {path}")
                    found = True
                    break
            
            if not found:
                print(f"  ✗ Image NOT found in any location")
                print(f"    Looking for: {os.path.basename(staff.image_path)}")
                
                # List what's actually in the folder
                images_folder = 'uploads/staff_images'
                if os.path.exists(images_folder):
                    files = os.listdir(images_folder)
                    print(f"    Files in folder: {files[:5]}")  # Show first 5 files
        print()