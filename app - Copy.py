from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
import io
import zipfile
import pandas as pd
from datetime import datetime
from PIL import Image, ImageEnhance
import base64
import numpy as np

from config import Config
from models import db, Staff, Admin, ImportLog
from utils import process_imported_staff, download_from_google_drive, save_image_file, clean_filename, init_db

# Import rembg
from rembg import remove
from rembg.session_factory import new_session

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create upload folders
os.makedirs(Config.STAFF_IMAGES_FOLDER, exist_ok=True)
os.makedirs(Config.STAFF_SIGNATURES_FOLDER, exist_ok=True)
os.makedirs(Config.CLEAN_SIGNATURES_FOLDER, exist_ok=True)

# Create rembg session
rembg_session = new_session("u2net")
print("✅ rembg loaded successfully")

@login_manager.user_loader
def load_user(user_id):
    user = Staff.query.get(int(user_id))
    if user:
        return user
    return Admin.query.get(int(user_id))

def save_image_from_data_url(data_url, folder, filename):
    """Save image from data URL to file"""
    if not data_url or not data_url.startswith('data:image'):
        return None
    
    try:
        header, encoded = data_url.split(',', 1)
        image_data = base64.b64decode(encoded)
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        return filepath
    except Exception as e:
        print(f"Error saving image from data URL: {e}")
        return None

# ==================== REMBG BACKGROUND REMOVAL ====================

def remove_signature_background(image_path, output_path):
    """Remove background using rembg AI"""
    try:
        # Read image
        with open(image_path, 'rb') as f:
            input_image = f.read()
        
        # Remove background using rembg
        output_image = remove(input_image, session=rembg_session)
        
        # Save the result
        with open(output_path, 'wb') as f:
            f.write(output_image)
        
        # Open and enhance the result
        img = Image.open(output_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Enhance contrast to make signature darker
        rgb = img.convert('RGB')
        enhancer = ImageEnhance.Contrast(rgb)
        rgb = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Sharpness(rgb)
        rgb = enhancer.enhance(2.0)
        
        # Combine with alpha
        result = Image.new('RGBA', rgb.size)
        result.paste(rgb, (0, 0))
        result.putalpha(img.split()[-1])
        
        # Crop to content
        bbox = result.getbbox()
        if bbox:
            padding = 10
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(result.width, bbox[2] + padding)
            bottom = min(result.height, bbox[3] + padding)
            result = result.crop((left, top, right, bottom))
        
        result.save(output_path, 'PNG')
        return True
        
    except Exception as e:
        print(f"Rembg error: {e}")
        return False

# ==================== ROUTES ====================

@app.route('/uploads/<folder>/<filename>')
def uploaded_file(folder, filename):
    filename = os.path.basename(filename)
    upload_path = os.path.join(Config.UPLOAD_FOLDER, folder)
    return send_from_directory(upload_path, filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type', 'staff')
        
        if user_type == 'admin':
            user = Admin.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                session['user_role'] = user.role
                session['user_type'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'danger')
        else:
            user = Staff.query.filter(
                (Staff.email == username) | (Staff.username == username) | (Staff.phone_number == username)
            ).first()
            if user and user.check_password(password):
                login_user(user)
                session['user_type'] = 'staff'
                return redirect(url_for('staff_dashboard'))
            else:
                flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        ministry = request.form.get('ministry')
        department = request.form.get('department')
        designation = request.form.get('designation')
        
        image_path = None
        photo_data = request.form.get('photo_data')
        photo_file = request.files.get('photo')
        
        if photo_data and photo_data.startswith('data:image'):
            filename = f"staff_{full_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            image_path = save_image_from_data_url(photo_data, Config.STAFF_IMAGES_FOLDER, filename)
        elif photo_file and photo_file.filename:
            filename = f"staff_{full_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            image_path = save_image_file(photo_file.read(), filename, Config.STAFF_IMAGES_FOLDER)
        
        signature_path = None
        signature_data = request.form.get('signature_data')
        signature_file = request.files.get('signature')
        
        if signature_data and signature_data.startswith('data:image'):
            filename = f"signature_{full_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            signature_path = save_image_from_data_url(signature_data, Config.STAFF_SIGNATURES_FOLDER, filename)
        elif signature_file and signature_file.filename:
            filename = f"signature_{full_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            signature_path = save_image_file(signature_file.read(), filename, Config.STAFF_SIGNATURES_FOLDER)
        
        if all([full_name, email, phone]):
            staff = Staff(
                full_name=full_name,
                email=email,
                phone_number=phone,
                ministry=ministry,
                department=department,
                designation=designation,
                image_path=image_path,
                signature_path=signature_path
            )
            
            db.session.add(staff)
            db.session.commit()
            
            flash('Registration submitted successfully! Admin will set your credentials.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Please fill all required fields', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    total_staff = Staff.query.count()
    total_admins = Admin.query.count()
    recent_imports = ImportLog.query.order_by(ImportLog.import_date.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html', 
                         total_staff=total_staff, 
                         total_admins=total_admins,
                         recent_imports=recent_imports)

@app.route('/admin/staff')
@login_required
def admin_staff():
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    search = request.args.get('search', '')
    if search:
        staff_list = Staff.query.filter(
            Staff.full_name.contains(search) | 
            Staff.email.contains(search) | 
            Staff.phone_number.contains(search)
        ).all()
    else:
        staff_list = Staff.query.all()
    
    return render_template('staff_list.html', staff=staff_list, search=search)

@app.route('/admin/staff/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_staff(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    staff = Staff.query.get_or_404(id)
    
    if request.method == 'POST':
        staff.username = request.form.get('username')
        staff.ministry = request.form.get('ministry')
        staff.department = request.form.get('department')
        staff.designation = request.form.get('designation')
        staff.updated_by = current_user.full_name
        
        new_password = request.form.get('password')
        if new_password:
            staff.set_password(new_password)
        
        db.session.commit()
        flash('Staff updated successfully', 'success')
        return redirect(url_for('admin_staff'))
    
    return render_template('edit_staff.html', staff=staff)

@app.route('/admin/staff/delete/<int:id>')
@login_required
def delete_staff(id):
    if session.get('user_type') != 'admin' or session.get('user_role') != 'super_admin':
        flash('Permission denied', 'danger')
        return redirect(url_for('admin_staff'))
    
    staff = Staff.query.get_or_404(id)
    
    if staff.image_path and os.path.exists(staff.image_path):
        os.remove(staff.image_path)
    if staff.signature_path and os.path.exists(staff.signature_path):
        os.remove(staff.signature_path)
    if staff.signature_bg_removed_path and os.path.exists(staff.signature_bg_removed_path):
        os.remove(staff.signature_bg_removed_path)
    
    db.session.delete(staff)
    db.session.commit()
    flash('Staff deleted successfully', 'success')
    return redirect(url_for('admin_staff'))

# ==================== SIGNATURE BACKGROUND REMOVAL ROUTES ====================

@app.route('/admin/staff/remove-bg/<int:id>')
@login_required
def remove_single_background(id):
    if session.get('user_type') != 'admin':
        flash('Unauthorized', 'danger')
        return redirect(url_for('admin_staff'))
    
    staff = Staff.query.get_or_404(id)
    
    if not staff.signature_path:
        flash('No signature found', 'warning')
        return redirect(url_for('admin_staff'))
    
    try:
        sig_filename = os.path.basename(staff.signature_path)
        sig_path = os.path.join('uploads', 'staff_signatures', sig_filename)
        
        if os.path.exists(sig_path):
            clean_filename = f"clean_{sig_filename}"
            clean_path = os.path.join(Config.CLEAN_SIGNATURES_FOLDER, clean_filename)
            
            flash('Processing with AI background removal...', 'info')
            
            success = remove_signature_background(sig_path, clean_path)
            
            if success:
                staff.signature_bg_removed_path = clean_filename
                db.session.commit()
                flash('✅ Background removed successfully!', 'success')
            else:
                flash('❌ Background removal failed', 'danger')
        else:
            flash('Signature file not found', 'danger')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('admin_staff'))

@app.route('/admin/bulk-remove-bg')
@login_required
def bulk_remove_backgrounds():
    if session.get('user_type') != 'admin':
        flash('Unauthorized', 'danger')
        return redirect(url_for('admin_staff'))
    
    staff_members = Staff.query.filter(
        Staff.signature_path.isnot(None),
        Staff.signature_bg_removed_path.is_(None)
    ).all()
    
    if not staff_members:
        flash('No signatures to process', 'info')
        return redirect(url_for('admin_staff'))
    
    processed = 0
    failed = 0
    
    for staff in staff_members:
        if staff.signature_path:
            try:
                sig_filename = os.path.basename(staff.signature_path)
                sig_path = os.path.join('uploads', 'staff_signatures', sig_filename)
                
                if os.path.exists(sig_path):
                    clean_filename = f"clean_{sig_filename}"
                    clean_path = os.path.join(Config.CLEAN_SIGNATURES_FOLDER, clean_filename)
                    
                    success = remove_signature_background(sig_path, clean_path)
                    
                    if success:
                        staff.signature_bg_removed_path = clean_filename
                        processed += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error processing {staff.full_name}: {e}")
                failed += 1
    
    db.session.commit()
    flash(f'✅ Processed: {processed} signatures, Failed: {failed}', 'success')
    return redirect(url_for('admin_staff'))

# ==================== IMPORT ROUTES ====================

@app.route('/admin/import', methods=['GET', 'POST'])
@login_required
def import_data():
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    if request.method == 'POST':
        file = request.files.get('file')
        sheet_url = request.form.get('sheet_url')
        
        df = None
        
        if file and file.filename:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        elif sheet_url:
            try:
                if '/d/' in sheet_url:
                    sheet_id = sheet_url.split('/d/')[1].split('/')[0]
                    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                    df = pd.read_csv(csv_url)
                elif 'pub?output=csv' in sheet_url:
                    df = pd.read_csv(sheet_url)
                else:
                    flash('Invalid Google Sheet URL', 'danger')
                    return redirect(url_for('import_data'))
            except Exception as e:
                flash(f'Error reading Google Sheet: {str(e)}', 'danger')
                return redirect(url_for('import_data'))
        
        if df is not None and not df.empty:
            successful, failed, errors = process_imported_staff(df, current_user.full_name)
            flash(f'Import completed! {successful} imported, {failed} failed', 'success')
            return redirect(url_for('admin_staff'))
        else:
            flash('No data found in file/sheet', 'danger')
    
    return render_template('import_data.html')

@app.route('/admin/signature-remover', methods=['GET', 'POST'])
@login_required
def signature_remover():
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    if request.method == 'POST':
        files = request.files.getlist('signatures')
        results = []
        
        for file in files:
            if file:
                temp_filename = f"temp_{file.filename}"
                temp_path = os.path.join(Config.CLEAN_SIGNATURES_FOLDER, temp_filename)
                file.save(temp_path)
                
                clean_filename = f"clean_{file.filename}"
                clean_path = os.path.join(Config.CLEAN_SIGNATURES_FOLDER, clean_filename)
                
                success = remove_signature_background(temp_path, clean_path)
                
                if success and os.path.exists(clean_path):
                    results.append({'name': file.filename, 'path': clean_path})
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        if results:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for r in results:
                    if os.path.exists(r['path']):
                        with open(r['path'], 'rb') as f:
                            zf.writestr(f"clean_{r['name']}", f.read())
            
            zip_buffer.seek(0)
            return send_file(zip_buffer, as_attachment=True, download_name='cleaned_signatures.zip')
    
    return render_template('signature_remover.html')

@app.route('/admin/download-all-signatures')
@login_required
def download_all_signatures():
    if session.get('user_type') != 'admin':
        return redirect(url_for('staff_dashboard'))
    
    zip_buffer = io.BytesIO()
    count = 0
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        staff_members = Staff.query.all()
        for staff in staff_members:
            sig_path = staff.signature_bg_removed_path or staff.signature_path
            if sig_path:
                folder = 'staff_signatures_clean' if staff.signature_bg_removed_path else 'staff_signatures'
                full_path = os.path.join('uploads', folder, os.path.basename(sig_path))
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        filename = f"{clean_filename(staff.full_name)}_signature.png"
                        zf.writestr(filename, f.read())
                        count += 1
    
    zip_buffer.seek(0)
    if count > 0:
        return send_file(zip_buffer, as_attachment=True, download_name=f'signatures_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip')
    else:
        flash('No signatures found to download', 'warning')
        return redirect(url_for('admin_staff'))

# ==================== ADMIN MANAGEMENT ROUTES ====================

@app.route('/admin/admins')
@login_required
def manage_admins():
    if session.get('user_type') != 'admin' or session.get('user_role') != 'super_admin':
        flash('Permission denied', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    admins = Admin.query.all()
    return render_template('manage_admins.html', admins=admins)

@app.route('/admin/admins/create', methods=['POST'])
@login_required
def create_admin():
    if session.get('user_role') != 'super_admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    username = request.form.get('username')
    email = request.form.get('email')
    full_name = request.form.get('full_name')
    password = request.form.get('password')
    role = request.form.get('role', 'admin')
    
    if Admin.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('manage_admins'))
    
    admin = Admin(username=username, email=email, full_name=full_name, role=role)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    
    flash('Admin created successfully', 'success')
    return redirect(url_for('manage_admins'))

@app.route('/admin/admins/reset-password/<int:id>', methods=['POST'])
@login_required
def reset_admin_password(id):
    if session.get('user_role') != 'super_admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    admin = Admin.query.get_or_404(id)
    new_password = request.form.get('password')
    
    if new_password:
        admin.set_password(new_password)
        db.session.commit()
        flash('Password reset successfully', 'success')
    
    return redirect(url_for('manage_admins'))

@app.route('/admin/admins/delete/<int:id>', methods=['POST'])
@login_required
def delete_admin(id):
    if session.get('user_role') != 'super_admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    admin = Admin.query.get_or_404(id)
    if admin.username == current_user.username:
        flash('Cannot delete your own account', 'danger')
        return redirect(url_for('manage_admins'))
    
    db.session.delete(admin)
    db.session.commit()
    flash('Admin deleted successfully', 'success')
    return redirect(url_for('manage_admins'))

# ==================== STAFF ROUTES ====================

@app.route('/staff/dashboard')
@login_required
def staff_dashboard():
    if session.get('user_type') != 'staff':
        return redirect(url_for('admin_dashboard'))
    
    return render_template('staff_dashboard.html', staff=current_user)

# ==================== RUN APP ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)