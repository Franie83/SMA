import streamlit as st
from rembg import remove
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import pandas as pd
import os
from datetime import datetime
import io
import base64
import hashlib
import re
import zipfile
import time
import numpy as np
import logging
import shutil
try:
    from rembg import remove
    REMBG_AVAILABLE = True
except (ImportError, ModuleNotFoundError, Exception) as e:
    REMBG_AVAILABLE = False
    st.warning("Advanced background removal is not available in this environment. Using basic mode.")
    
    # Define a dummy remove function
    def remove(x):
        return x

# Configure logging
logging.basicConfig(level=logging.INFO)

# Page configuration
st.set_page_config(page_title="Staff Management System", page_icon="📝", layout="wide")

# Excel file paths
STAFF_EXCEL_FILE = "staff_registrations.xlsx"
ADMIN_EXCEL_FILE = "admin_users.xlsx"

# Download folders
DOWNLOAD_FOLDER = "downloads"
PHOTOS_DOWNLOAD_FOLDER = os.path.join(DOWNLOAD_FOLDER, "photos")
SIGNATURES_DOWNLOAD_FOLDER = os.path.join(DOWNLOAD_FOLDER, "signatures")

# Create download folders
os.makedirs(PHOTOS_DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(SIGNATURES_DOWNLOAD_FOLDER, exist_ok=True)

# Load logo
LOGO_PATH = "background_image/mcde-logo.jpeg"
logo_base64 = None
if os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as img_file:
        logo_base64 = base64.b64encode(img_file.read()).decode()

# Custom CSS for logo, footer, and buttons
st.markdown(
    f"""
    <style>
    .logo-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: -60px;
        margin-bottom: 10px;
        z-index: 999;
    }}
    .logo-container img {{
        max-height: 80px;
        width: auto;
    }}
    .footer {{
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        text-align: center;
        padding: 10px;
        background-color: rgba(0, 0, 0, 0.8);
        color: white;
        font-size: 14px;
        z-index: 999;
    }}
    .stButton > button {{
        width: 100%;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Display global logo at top center
if logo_base64:
    st.markdown(
        f"""
        <div class="logo-container">
            <img src="data:image/jpeg;base64,{logo_base64}" alt="MCDE Logo">
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning(f"Logo not found at {LOGO_PATH}")

# Footer
st.markdown(
    """
    <div class="footer">
        Powered by Ministry of Communication and Digital Economy, Edo State!
    </div>
    """,
    unsafe_allow_html=True
)

# Initialize session state
if 'stop_processing' not in st.session_state:
    st.session_state.stop_processing = False
if 'processing_active' not in st.session_state:
    st.session_state.processing_active = False
if 'show_password' not in st.session_state:
    st.session_state.show_password = False
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'editing_staff_id' not in st.session_state:
    st.session_state.editing_staff_id = None
if 'show_camera_photo' not in st.session_state:
    st.session_state.show_camera_photo = False
if 'show_camera_signature' not in st.session_state:
    st.session_state.show_camera_signature = False
if 'show_draw_signature' not in st.session_state:
    st.session_state.show_draw_signature = False
if 'captured_photo' not in st.session_state:
    st.session_state.captured_photo = None
if 'captured_signature' not in st.session_state:
    st.session_state.captured_signature = None
if 'drawn_signature' not in st.session_state:
    st.session_state.drawn_signature = None
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None
if 'show_signature_remover' not in st.session_state:
    st.session_state.show_signature_remover = False

# ==================== SIGNATURE BACKGROUND REMOVAL FUNCTIONS ====================

def remove_signature_background_preserve(signature_bytes):
    """
    High-quality background removal that preserves ALL signature strokes
    with adaptive thresholding and enhanced clarity.
    """
    if signature_bytes is None:
        return None

    try:
        # Remove background
        output_data = remove(signature_bytes)
        result_image = Image.open(io.BytesIO(output_data))

        # Ensure RGBA
        if result_image.mode != 'RGBA':
            result_image = result_image.convert('RGBA')

        r, g, b, alpha = result_image.split()
        alpha_array = np.array(alpha)

        # Adaptive threshold (better for different image qualities)
        threshold = np.percentile(alpha_array, 5)
        alpha_array = np.where(alpha_array < threshold, 0, alpha_array)

        # Smooth edges slightly
        alpha_smoothed = Image.fromarray(alpha_array.astype('uint8'))
        alpha_smoothed = alpha_smoothed.filter(ImageFilter.GaussianBlur(radius=0.1))

        result_image.putalpha(alpha_smoothed)

        # Enhance signature visibility
        rgb_image = result_image.convert('RGB')

        # Increase contrast
        contrast = ImageEnhance.Contrast(rgb_image)
        rgb_enhanced = contrast.enhance(1.8)

        # Increase sharpness
        sharpness = ImageEnhance.Sharpness(rgb_enhanced)
        rgb_enhanced = sharpness.enhance(5)

        # Slight brightness boost
        brightness = ImageEnhance.Brightness(rgb_enhanced)
        rgb_enhanced = brightness.enhance(1.07)

        # Combine back with alpha
        result_enhanced = Image.new('RGBA', result_image.size)
        result_enhanced.paste(rgb_enhanced, (0, 0))
        result_enhanced.putalpha(alpha_smoothed)

        # Crop safely using mask
        mask = np.array(alpha_smoothed) > 10
        if np.any(mask):
            coords = np.argwhere(mask)
            top, left = coords.min(axis=0)
            bottom, right = coords.max(axis=0)

            padding = 30
            left = max(0, left - padding)
            top = max(0, top - padding)
            right = min(result_enhanced.width, right + padding)
            bottom = min(result_enhanced.height, bottom + padding)

            result_enhanced = result_enhanced.crop((left, top, right, bottom))

        # Convert to bytes
        img_buffer = io.BytesIO()
        result_enhanced.save(img_buffer, format='PNG')

        return img_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error removing background: {e}")
        st.error(f"Error removing background: {str(e)}")
        return None


def remove_signature_background_simple(signature_bytes):
    """
    Faster lightweight version (no adaptive threshold).
    """
    if signature_bytes is None:
        return None

    try:
        output_data = remove(signature_bytes)
        result_image = Image.open(io.BytesIO(output_data))

        if result_image.mode != 'RGBA':
            result_image = result_image.convert('RGBA')

        r, g, b, alpha = result_image.split()
        alpha_array = np.array(alpha)

        alpha_array = np.where(alpha_array < 15, 0, alpha_array)

        alpha_cleaned = Image.fromarray(alpha_array.astype('uint8'))
        alpha_cleaned = alpha_cleaned.filter(ImageFilter.GaussianBlur(radius=0.2))

        result_image.putalpha(alpha_cleaned)

        # Enhance
        rgb = result_image.convert('RGB')

        contrast = ImageEnhance.Contrast(rgb)
        rgb_enhanced = contrast.enhance(1.3)

        sharpness = ImageEnhance.Sharpness(rgb_enhanced)
        rgb_enhanced = sharpness.enhance(1.2)

        final = Image.new('RGBA', result_image.size)
        final.paste(rgb_enhanced, (0, 0))
        final.putalpha(alpha_cleaned)

        bbox = final.getbbox()
        if bbox:
            padding = 25
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(final.width, bbox[2] + padding)
            bottom = min(final.height, bbox[3] + padding)
            final = final.crop((left, top, right, bottom))

        img_buffer = io.BytesIO()
        final.save(img_buffer, format='PNG')

        return img_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error removing background: {e}")
        st.error(f"Error removing background: {str(e)}")
        return None


def save_clean_signature_to_file(signature_bytes, filename):
    """
    Save cleaned signature to disk safely
    """
    if signature_bytes is None:
        return None

    folder = "staff_signatures_clean"
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)

    with open(filepath, 'wb') as f:
        f.write(signature_bytes)

    return filepath


def process_signature_background(signature_path, staff_id, staff_name):
    """
    Process a single signature
    """
    if not os.path.exists(signature_path):
        return None

    try:
        with open(signature_path, 'rb') as f:
            signature_bytes = f.read()

        cleaned_signature = remove_signature_background_preserve(signature_bytes)

        if cleaned_signature:
            clean_name = re.sub(r'[^\w\s-]', '', staff_name).strip().replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename = f"{clean_name}_{timestamp}.png"

            return save_clean_signature_to_file(cleaned_signature, filename)

        return None

    except Exception as e:
        logging.error(f"Error processing signature for {staff_name}: {e}")
        return None


# ==================== SIGNATURE REMOVER APP ====================

def signature_remover_app():
    """Signature Background Remover sub-app"""
    st.title("✍️ Signature Background Remover")
    st.markdown("Upload or capture signature images to remove backgrounds")
    
    # Back button
    if st.button("← Back to Staff Management", use_container_width=True):
        st.session_state.show_signature_remover = False
        st.rerun()
    
    st.markdown("---")
    
    # Initialize session state for this sub-app
    if 'sig_remover_stop_processing' not in st.session_state:
        st.session_state.sig_remover_stop_processing = False
    if 'sig_remover_captured_image' not in st.session_state:
        st.session_state.sig_remover_captured_image = None
    if 'sig_remover_show_camera' not in st.session_state:
        st.session_state.sig_remover_show_camera = False
    if 'confirm_admin_delete' not in st.session_state:
        st.session_state.confirm_admin_delete = None
    
    # Create output folder
    OUTPUT_FOLDER = "processed_signatures"
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    def remove_background_simple(image_bytes):
        if image_bytes is None:
            return None
        try:
            output = remove(image_bytes)
            result_img = Image.open(io.BytesIO(output))
            if result_img.mode != 'RGBA':
                result_img = result_img.convert('RGBA')
            enhancer = ImageEnhance.Contrast(result_img)
            result_img = enhancer.enhance(1.5)
            img_buffer = io.BytesIO()
            result_img.save(img_buffer, format='PNG')
            return img_buffer.getvalue()
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None
    
    def clean_filename(filename):
        name, ext = os.path.splitext(filename)
        clean_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
        return f"{clean_name}_transparent.png"
    
    def save_signature_to_file(signature_bytes, original_filename):
        if signature_bytes is None:
            return None
        clean_name = clean_filename(original_filename)
        filepath = os.path.join(OUTPUT_FOLDER, clean_name)
        with open(filepath, 'wb') as f:
            f.write(signature_bytes)
        return filepath
    
    def process_single_image(image_data, original_filename):
        try:
            cleaned_signature = remove_background_simple(image_data)
            if cleaned_signature:
                saved_path = save_signature_to_file(cleaned_signature, original_filename)
                return {
                    'success': True,
                    'original_name': original_filename,
                    'saved_name': clean_filename(original_filename),
                    'saved_path': saved_path,
                    'image_bytes': cleaned_signature
                }
            else:
                return {'success': False, 'original_name': original_filename, 'error': 'Background removal failed'}
        except Exception as e:
            return {'success': False, 'original_name': original_filename, 'error': str(e)}
    
    def download_single_image(image_bytes, filename):
        b64 = base64.b64encode(image_bytes).decode()
        href = f'<a href="data:image/png;base64,{b64}" download="{filename}">📥 Download</a>'
        return href
    
    # Tabs
    tab1, tab2 = st.tabs(["📁 Upload Images", "📷 Capture Signature"])
    
    all_images = []
    
    # Tab 1: File Upload
    with tab1:
        uploaded_files = st.file_uploader(
            "Choose signature images",
            type=['png', 'jpg', 'jpeg', 'bmp', 'webp', 'jfif'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            for file in uploaded_files:
                all_images.append({
                    'data': file.getvalue(),
                    'name': file.name
                })
            
            st.write(f"📁 {len(uploaded_files)} file(s) uploaded")
            
            with st.expander("Preview Uploaded Images"):
                cols = st.columns(min(3, len(uploaded_files)))
                for idx, file in enumerate(uploaded_files[:6]):
                    with cols[idx % 3]:
                        st.image(file, caption=file.name, use_container_width=True)
    
    # Tab 2: Camera Capture
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📷 Take Photo", use_container_width=True):
                st.session_state.sig_remover_show_camera = True
        
        with col2:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.sig_remover_captured_image = None
                st.session_state.sig_remover_show_camera = False
                st.rerun()
        
        if st.session_state.sig_remover_show_camera:
            captured_image = st.camera_input("Capture signature", key="sig_remover_camera")
            if captured_image:
                st.session_state.sig_remover_captured_image = captured_image
                st.session_state.sig_remover_show_camera = False
                st.rerun()
        
        if st.session_state.sig_remover_captured_image:
            st.success("✅ Signature captured!")
            st.image(st.session_state.sig_remover_captured_image, width=250)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            captured_name = f"captured_{timestamp}.png"
            
            all_images.append({
                'data': st.session_state.sig_remover_captured_image.getvalue(),
                'name': captured_name
            })
    
    # Process Button
    if all_images:
        st.markdown("---")
        st.write(f"**Total images to process:** {len(all_images)}")
        
        if st.button("🚀 Remove Background", type="primary", use_container_width=True):
            results = []
            processed = 0
            failed = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, img_data in enumerate(all_images):
                status_text.text(f"Processing ({idx+1}/{len(all_images)}): {img_data['name']}")
                progress_bar.progress((idx) / len(all_images))
                
                result = process_single_image(img_data['data'], img_data['name'])
                results.append(result)
                
                if result['success']:
                    processed += 1
                else:
                    failed += 1
                
                progress_bar.progress((idx + 1) / len(all_images))
            
            progress_bar.progress(1.0)
            status_text.text(f"✅ Complete! Processed: {processed}, Failed: {failed}")
            
            st.session_state.sig_remover_results = results
            
            # Display results
            st.markdown("---")
            st.subheader("📊 Results")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total", len(all_images))
            col2.metric("Success", processed)
            col3.metric("Failed", failed)
            
            # Download all as ZIP
            successful = [r for r in results if r['success']]
            if successful:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for r in successful:
                        zf.writestr(r['saved_name'], r['image_bytes'])
                
                zip_buffer.seek(0)
                st.download_button(
                    label=f"📦 Download ALL ({len(successful)} files) as ZIP",
                    data=zip_buffer,
                    file_name=f"signatures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            
            # Individual results
            st.markdown("---")
            st.subheader("📄 Individual Results")
            
            for result in results:
                if result['success']:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**{result['original_name']}** → {result['saved_name']}")
                    with col2:
                        img = Image.open(io.BytesIO(result['image_bytes']))
                        st.image(img, width=60)
                    with col3:
                        href = download_single_image(result['image_bytes'], result['saved_name'])
                        st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error(f"❌ {result['original_name']}: {result['error']}")
            
            # Save to folder button
            if st.button("💾 Save to Local Folder", use_container_width=True):
                saved = 0
                for r in successful:
                    if r['saved_path']:
                        saved += 1
                st.success(f"✅ Saved {saved} files to '{OUTPUT_FOLDER}' folder!")


# ==================== DOWNLOAD FUNCTIONS ====================

def download_photo_to_folder(image_bytes, filename):
    """Save photo to downloads folder"""
    if image_bytes is None:
        return None
    
    filepath = os.path.join(PHOTOS_DOWNLOAD_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    return filepath


def download_signature_to_folder(signature_bytes, filename):
    """Save signature to downloads folder"""
    if signature_bytes is None:
        return None
    
    filepath = os.path.join(SIGNATURES_DOWNLOAD_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(signature_bytes)
    return filepath


def download_all_photos_to_folder(df):
    """Download all profile photos to folder"""
    count = 0
    for _, row in df.iterrows():
        if is_valid_path(row['image_path']):
            try:
                with open(row['image_path'], 'rb') as f:
                    clean_name = clean_filename(row['full_name'])
                    filename = f"{clean_name}_photo.png"
                    filepath = os.path.join(PHOTOS_DOWNLOAD_FOLDER, filename)
                    shutil.copy2(row['image_path'], filepath)
                    count += 1
            except:
                pass
    return count


def download_all_signatures_to_folder(df):
    """Download all signatures to folder"""
    count = 0
    for _, row in df.iterrows():
        sig_path = row['signature_bg_removed_path'] if row['signature_bg_removed_path'] else row['signature_path']
        if is_valid_path(sig_path):
            try:
                clean_name = clean_filename(row['full_name'])
                if row['signature_bg_removed_path']:
                    filename = f"{clean_name}_signature_clean.png"
                else:
                    filename = f"{clean_name}_signature.png"
                filepath = os.path.join(SIGNATURES_DOWNLOAD_FOLDER, filename)
                shutil.copy2(sig_path, filepath)
                count += 1
            except:
                pass
    return count

# ==================== HELPER FUNCTIONS ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def clean_filename(name):
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

def make_circular_image(image, size=(150, 150)):
    """Convert an image to circular format with transparent background"""
    if image is None:
        return None
    
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    image = image.resize(size, Image.Resampling.LANCZOS)
    
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    
    circular_image = Image.new('RGBA', size, (0, 0, 0, 0))
    circular_image.paste(image, (0, 0), mask)
    
    return circular_image

def is_valid_path(path):
    if path is None:
        return False
    if isinstance(path, float) and np.isnan(path):
        return False
    if isinstance(path, str) and path == "":
        return False
    if isinstance(path, str) and os.path.exists(path):
        return True
    return False

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    phone = str(phone).strip()
    phone = re.sub(r'[\s\-\.\(\)]', '', phone)
    if not phone:
        return False
    if phone.isdigit() and 10 <= len(phone) <= 15:
        return True
    return False

def image_to_bytes(image):
    if image is None:
        return None
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    return img_buffer.getvalue()

def bytes_to_image(bytes_data):
    if bytes_data is None:
        return None
    return Image.open(io.BytesIO(bytes_data))

def save_image_to_file(image_bytes, filename):
    if image_bytes is None:
        return None
    filepath = os.path.join("staff_images", filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    return filepath

def save_signature_to_file(signature_bytes, filename):
    if signature_bytes is None:
        return None
    filepath = os.path.join("staff_signatures", filename)
    with open(filepath, 'wb') as f:
        f.write(signature_bytes)
    return filepath

def get_next_id(df):
    if df.empty:
        return 1
    return df['id'].max() + 1

def get_unique_ministries():
    """Get unique ministries from the database for dropdown"""
    try:
        if os.path.exists(STAFF_EXCEL_FILE):
            df = pd.read_excel(STAFF_EXCEL_FILE)
            if not df.empty and 'ministry' in df.columns:
                ministries = df['ministry'].dropna().unique()
                ministries = [m for m in ministries if m and str(m).strip() and str(m) != 'nan']
                return sorted(ministries)
    except Exception as e:
        print(f"Error reading ministries: {e}")
    return []

def search_staff(df, search_term):
    """Search staff by multiple fields with wildcard support"""
    if not search_term:
        return df
    
    search_term = search_term.lower().strip()
    
    mask = (
        df['full_name'].str.lower().str.contains(search_term, na=False, regex=False) |
        df['email'].str.lower().str.contains(search_term, na=False, regex=False) |
        df['phone_number'].astype(str).str.contains(search_term, na=False, regex=False) |
        df['username'].str.lower().str.contains(search_term, na=False, regex=False) |
        df['ministry'].str.lower().str.contains(search_term, na=False, regex=False) |
        df['department'].str.lower().str.contains(search_term, na=False, regex=False) |
        df['designation'].str.lower().str.contains(search_term, na=False, regex=False)
    )
    
    return df[mask]

def safe_read_excel(filepath):
    """Safely read Excel file with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if os.path.exists(filepath):
                return pd.read_excel(filepath)
            else:
                return pd.DataFrame()
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                st.error(f"Cannot read {filepath}. Please close the file if it's open in Excel and refresh the page.")
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return pd.DataFrame()

def safe_write_excel(df, filepath):
    """Safely write Excel file with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df.to_excel(filepath, index=False)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                st.error(f"Cannot write to {filepath}. Please close the file if it's open in Excel.")
                return False
        except Exception as e:
            st.error(f"Error writing file: {e}")
            return False

# Initialize Excel files as database
def init_excel_files():
    os.makedirs("staff_images", exist_ok=True)
    os.makedirs("staff_signatures", exist_ok=True)
    os.makedirs("staff_signatures_clean", exist_ok=True)
    
    if os.path.exists(STAFF_EXCEL_FILE):
        try:
            df_test = safe_read_excel(STAFF_EXCEL_FILE)
            if not df_test.empty and ('status' in df_test.columns or 'approved_at' in df_test.columns):
                backup_name = f"staff_registrations_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                try:
                    os.rename(STAFF_EXCEL_FILE, backup_name)
                    st.warning(f"Old database format detected. Backed up to {backup_name} and created new database.")
                except:
                    pass
        except:
            pass
    
    if not os.path.exists(STAFF_EXCEL_FILE):
        staff_df = pd.DataFrame(columns=[
            'id', 'full_name', 'email', 'phone_number', 'ministry', 'department', 
            'designation', 'image_path', 'signature_path', 'signature_bg_removed_path',
            'username', 'password', 'registered_at', 'updated_at', 'updated_by'
        ])
        safe_write_excel(staff_df, STAFF_EXCEL_FILE)
    
    if not os.path.exists(ADMIN_EXCEL_FILE):
        admin_df = pd.DataFrame(columns=['id', 'username', 'password', 'email', 'full_name', 'role'])
        safe_write_excel(admin_df, ADMIN_EXCEL_FILE)
        add_default_admins()

def add_default_admins():
    """Add default admin and super admin users"""
    admin_df = safe_read_excel(ADMIN_EXCEL_FILE)
    
    if admin_df.empty:
        # Add Super Admin
        super_admin_password = hash_password("superadmin123")
        super_admin = pd.DataFrame([{
            'id': 1,
            'username': 'superadmin',
            'password': super_admin_password,
            'email': 'superadmin@system.com',
            'full_name': 'Super Administrator',
            'role': 'super_admin'
        }])
        
        # Add Regular Admin
        admin_password = hash_password("admin123")
        regular_admin = pd.DataFrame([{
            'id': 2,
            'username': 'admin',
            'password': admin_password,
            'email': 'admin@system.com',
            'full_name': 'System Administrator',
            'role': 'admin'
        }])
        
        admin_df = pd.concat([super_admin, regular_admin], ignore_index=True)
        safe_write_excel(admin_df, ADMIN_EXCEL_FILE)
        
        st.info("Default users created: superadmin/superadmin123 and admin/admin123")

def clean_database():
    """Remove empty/invalid rows from the database"""
    if os.path.exists(STAFF_EXCEL_FILE):
        try:
            df = safe_read_excel(STAFF_EXCEL_FILE)
            if not df.empty:
                df = df[df['full_name'].notna()]
                df = df[df['full_name'] != '']
                df = df[df['full_name'].astype(str).str.strip() != '']
                df = df.reset_index(drop=True)
                safe_write_excel(df, STAFF_EXCEL_FILE)
                return df
        except Exception as e:
            print(f"Error cleaning database: {e}")
    return pd.DataFrame()

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_type' not in st.session_state:
    st.session_state.user_type = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0

init_excel_files()
try:
    clean_database()
except Exception as e:
    st.warning(f"Note: Database file may be open in another program. Please close Excel if open.")

# ==================== REGISTRATION FORM ====================
def end_user_registration():
    st.title("📝 Staff Registration Form")
    st.write("Please fill in your details below. Admin will set your login credentials.")
    
    st.subheader("📸 Capture Options")
    col_cam1, col_cam2, col_cam3, col_cam4 = st.columns(4)
    
    with col_cam1:
        if st.button("📷 Capture Selfie (Front Camera)", use_container_width=True, key="cam_selfie"):
            st.session_state.show_camera_photo = True
            st.session_state.show_camera_signature = False
            st.session_state.show_draw_signature = False
    
    with col_cam2:
        if st.button("📸 Capture Photo (Back Camera)", use_container_width=True, key="cam_photo"):
            st.session_state.show_camera_photo = True
            st.session_state.show_camera_signature = False
            st.session_state.show_draw_signature = False
    
    with col_cam3:
        if st.button("📷 Capture Signature (Camera)", use_container_width=True, key="cam_signature"):
            st.session_state.show_camera_signature = True
            st.session_state.show_camera_photo = False
            st.session_state.show_draw_signature = False
    
    with col_cam4:
        if st.button("✍️ Draw Signature", use_container_width=True, key="draw_sig"):
            st.session_state.show_draw_signature = True
            st.session_state.show_camera_photo = False
            st.session_state.show_camera_signature = False
    
    if st.session_state.show_camera_photo:
        st.subheader("Take a Photo")
        captured_image = st.camera_input("Capture", key="photo_camera_input")
        if captured_image:
            st.session_state.captured_photo = Image.open(captured_image)
            st.session_state.show_camera_photo = False
            st.rerun()
    
    if st.session_state.show_camera_signature:
        st.subheader("Capture Signature")
        captured_signature = st.camera_input("Capture", key="signature_camera_input")
        if captured_signature:
            st.session_state.captured_signature = Image.open(captured_signature)
            st.session_state.show_camera_signature = False
            st.rerun()
    
    if st.session_state.show_draw_signature:
        st.subheader("Draw Your Signature")
        from streamlit_drawable_canvas import st_canvas
        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            width=600,
            height=200,
            drawing_mode="freedraw",
            key="signature_canvas_draw",
        )
        if canvas_result.image_data is not None:
            st.session_state.drawn_signature = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
            st.session_state.show_draw_signature = False
            st.rerun()
    
    st.markdown("---")
    
    form_key = f"registration_form_{st.session_state.form_key}"
    
    with st.form(key=form_key):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name *")
            email = st.text_input("Email Address *")
            phone_number = st.text_input("Phone Number *")
            
            ministries = get_unique_ministries()
            if ministries:
                ministry_options = ["Select Ministry"] + ministries + ["Other (Enter New)"]
                ministry_selection = st.selectbox("Ministry *", options=ministry_options)
                
                if ministry_selection == "Other (Enter New)":
                    ministry = st.text_input("Enter New Ministry", placeholder="Type new ministry name")
                elif ministry_selection == "Select Ministry":
                    ministry = ""
                else:
                    ministry = ministry_selection
            else:
                ministry = st.text_input("Ministry *", placeholder="Enter ministry name")
                st.info("💡 Tip: Ministries from existing staff will appear here for easy selection")
        
        with col2:
            department = st.text_input("Department *")
            designation = st.text_input("Designation *")
        
        st.markdown("---")
        
        st.subheader("📸 Profile Photo")
        
        if st.session_state.captured_photo:
            st.image(st.session_state.captured_photo, caption=None, width=200)
            photo_to_save = st.session_state.captured_photo
        else:
            uploaded_photo = st.file_uploader("Or upload photo", type=['png', 'jpg', 'jpeg'], key="photo_upload_input")
            if uploaded_photo:
                photo_to_save = Image.open(uploaded_photo)
                st.image(photo_to_save, caption=None, width=200)
            else:
                photo_to_save = None
        
        st.markdown("---")
        
        st.subheader("✍️ Signature")
        
        if st.session_state.captured_signature:
            st.image(st.session_state.captured_signature, caption=None, width=250)
            signature_to_save = st.session_state.captured_signature
        elif st.session_state.drawn_signature:
            st.image(st.session_state.drawn_signature, caption=None, width=250)
            signature_to_save = st.session_state.drawn_signature
        else:
            uploaded_signature = st.file_uploader("Or upload signature", type=['png', 'jpg', 'jpeg'], key="signature_upload_input")
            if uploaded_signature:
                signature_to_save = Image.open(uploaded_signature)
                st.image(signature_to_save, caption=None, width=250)
            else:
                signature_to_save = None
        
        submitted = st.form_submit_button("✅ Submit Registration", type="primary", use_container_width=True)
        
        if submitted:
            errors = []
            if not full_name:
                errors.append("Full Name is required")
            if not email:
                errors.append("Email is required")
            elif not is_valid_email(email):
                errors.append(f"Invalid email: {email}")
            if not phone_number:
                errors.append("Phone is required")
            elif not is_valid_phone(phone_number):
                errors.append(f"Invalid phone: {phone_number}")
            if not ministry:
                errors.append("Ministry is required")
            if not department:
                errors.append("Department is required")
            if not designation:
                errors.append("Designation is required")
            if photo_to_save is None:
                errors.append("Profile photo is required")
            if signature_to_save is None:
                errors.append("Signature is required")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    df = safe_read_excel(STAFF_EXCEL_FILE)
                    
                    if not df.empty:
                        if email in df['email'].values:
                            st.error("Email already registered!")
                            return
                        if phone_number in df['phone_number'].values:
                            st.error("Phone number already registered!")
                            return
                    
                    new_id = get_next_id(df)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_filename = f"staff_{new_id}_{timestamp}.png"
                    signature_filename = f"signature_{new_id}_{timestamp}.png"
                    
                    image_path = save_image_to_file(image_to_bytes(photo_to_save), image_filename)
                    signature_path = save_signature_to_file(image_to_bytes(signature_to_save), signature_filename)
                    
                    new_record = pd.DataFrame([{
                        'id': new_id,
                        'full_name': full_name,
                        'email': email,
                        'phone_number': phone_number,
                        'ministry': ministry,
                        'department': department,
                        'designation': designation,
                        'image_path': image_path,
                        'signature_path': signature_path,
                        'signature_bg_removed_path': None,
                        'username': None,
                        'password': None,
                        'registered_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'updated_at': None,
                        'updated_by': None
                    }])
                    
                    df = pd.concat([df, new_record], ignore_index=True)
                    if safe_write_excel(df, STAFF_EXCEL_FILE):
                        st.session_state.captured_photo = None
                        st.session_state.captured_signature = None
                        st.session_state.drawn_signature = None
                        
                        st.success("✅ Registration submitted successfully!")
                        st.info("Admin will set your login credentials. Please check back later.")
                        st.balloons()
                        
                        st.session_state.form_key += 1
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Failed to save data. Please make sure the Excel file is not open.")
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ==================== STAFF LOGIN ====================
def end_user_login():
    st.title("🔐 Staff Login")
    st.info("Login using your Email, Phone Number, or Username")
    
    with st.form("staff_login_form"):
        email_phone_username = st.text_input("Email, Phone Number, or Username")
        password = st.text_input("Password", type="password")
        
        submitted = st.form_submit_button("Login", type="primary")
        
        if submitted:
            df = safe_read_excel(STAFF_EXCEL_FILE)
            
            user = df[
                (df['email'] == email_phone_username) | 
                (df['phone_number'] == email_phone_username) |
                (df['username'] == email_phone_username)
            ]
            
            if not user.empty:
                user = user.iloc[0]
                stored_password = user['password']
                if stored_password and not pd.isna(stored_password):
                    if stored_password == password or verify_password(password, stored_password):
                        st.session_state.logged_in = True
                        st.session_state.user_type = "staff"
                        st.session_state.user_id = user['id']
                        st.session_state.user_name = user['full_name']
                        st.success(f"Welcome {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid password!")
                else:
                    st.error("Credentials not set by admin yet! Please contact administrator.")
            else:
                st.error("No account found! Please check your email, phone number, or username.")

def staff_dashboard():
    st.title(f"👋 Welcome, {st.session_state.user_name}")
    
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🚪 Logout", key="staff_logout"):
            for key in ['logged_in', 'user_type', 'user_id', 'user_name', 'show_password']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    df = safe_read_excel(STAFF_EXCEL_FILE)
    staff = df[df['id'] == st.session_state.user_id].iloc[0]
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Profile Photo")
        if is_valid_path(staff['image_path']):
            with open(staff['image_path'], 'rb') as f:
                img = bytes_to_image(f.read())
                circular_img = make_circular_image(img, size=(200, 200))
                st.image(circular_img, caption=None, width=200)
        else:
            st.info("No photo uploaded")
        
        st.subheader("Signature")
        sig_path = staff['signature_bg_removed_path'] if is_valid_path(staff['signature_bg_removed_path']) else staff['signature_path']
        if is_valid_path(sig_path):
            with open(sig_path, 'rb') as f:
                img = bytes_to_image(f.read())
                circular_sig = make_circular_image(img, size=(200, 200))
                st.image(circular_sig, caption=None, width=200)
        else:
            st.info("No signature uploaded")
    
    with col2:
        st.subheader("Personal Information")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write(f"**Full Name:** {staff['full_name']}")
            st.write(f"**Email:** {staff['email']}")
            st.write(f"**Phone Number:** {staff['phone_number']}")
            st.write(f"**Ministry:** {staff['ministry']}")
        
        with col_b:
            st.write(f"**Department:** {staff['department']}")
            st.write(f"**Designation:** {staff['designation']}")
            if staff['registered_at'] and not pd.isna(staff['registered_at']):
                st.write(f"**Registered:** {str(staff['registered_at'])[:10]}")
        
        st.markdown("---")
        st.subheader("🔐 Your Login Credentials")
        
        cred_col1, cred_col2 = st.columns(2)
        with cred_col1:
            st.info(f"**Username:** `{staff['username'] if staff['username'] and not pd.isna(staff['username']) else 'Not set by admin yet'}`")
            st.info(f"**Email (for login):** `{staff['email']}`")
        with cred_col2:
            st.info(f"**Phone (for login):** `{staff['phone_number']}`")
            
            if staff['password'] and not pd.isna(staff['password']):
                pass_col1, pass_col2 = st.columns([3, 1])
                with pass_col1:
                    if st.session_state.show_password:
                        st.info(f"**Password:** `{staff['password']}`")
                    else:
                        st.info(f"**Password:** `{'•' * 8}`")
                with pass_col2:
                    if st.button("👁️" if not st.session_state.show_password else "🙈", 
                               key="toggle_password_staff",
                               help="Show/Hide Password"):
                        st.session_state.show_password = not st.session_state.show_password
                        st.rerun()
            else:
                st.info("**Password:** Not set by admin yet")
        
        st.success("💡 **Login Options:** You can login using your Email, Phone Number, or Username")
        
        if not staff['username'] or pd.isna(staff['username']) or not staff['password'] or pd.isna(staff['password']):
            st.warning("⚠️ Your login credentials have not been set by the administrator yet. Please contact admin.")

# ==================== ADMIN FUNCTIONS ====================
def admin_login():
    st.subheader("Admin Login")
    
    if not os.path.exists(ADMIN_EXCEL_FILE) or safe_read_excel(ADMIN_EXCEL_FILE).empty:
        add_default_admins()
    
    with st.form("admin_login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", type="primary"):
            admin_df = safe_read_excel(ADMIN_EXCEL_FILE)
            admin = admin_df[admin_df['username'] == username]
            
            if not admin.empty and verify_password(password, admin.iloc[0]['password']):
                st.session_state.logged_in = True
                st.session_state.user_type = "admin"
                st.session_state.user_id = admin.iloc[0]['id']
                st.session_state.user_name = admin.iloc[0]['full_name']
                st.session_state.user_role = admin.iloc[0]['role']
                st.success(f"Welcome {admin.iloc[0]['full_name']} ({admin.iloc[0]['role']})!")
                st.rerun()
            else:
                st.error("Invalid credentials! Use admin/admin123 or superadmin/superadmin123")

# ==================== PASSWORD MANAGER (Method 5) ====================

def admin_password_manager():
    """Admin password management page - Only accessible to Super Admin"""
    st.title("🔐 Admin Password Manager")
    
    # Check if user is super admin
    if 'user_role' not in st.session_state or st.session_state.user_role != 'super_admin':
        st.error("⚠️ Only Super Admin can access this page!")
        st.info("You need Super Admin privileges to manage admin passwords.")
        return
    
    st.success("👑 You are logged in as Super Administrator")
    st.markdown("Here you can manage all admin user passwords and delete admin accounts.")
    
    admin_df = safe_read_excel(ADMIN_EXCEL_FILE)
    
    if admin_df.empty:
        st.warning("No admin users found!")
        return
    
    st.markdown("---")
    
    # Display current admin users in a table format
    st.subheader("📋 Current Admin Users")
    
    for idx, row in admin_df.iterrows():
        with st.container():
            # Show role with appropriate icon
            role_icon = "👑" if row['role'] == 'super_admin' else "🛡️"
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            
            with col1:
                st.markdown(f"{role_icon} **{row['username'].upper()}**")
            with col2:
                st.write(f"Role: `{row['role']}`")
            with col3:
                st.write(f"Email: {row['email']}")
            with col4:
                # Delete button - but prevent deleting your own account
                if row['username'] != st.session_state.user_name:
                    if st.button(f"🗑️ Delete", key=f"del_admin_{row['id']}"):
                        st.session_state.confirm_admin_delete = row['id']
                        st.rerun()
                else:
                    st.info("Current user")
            
            # Show confirmation dialog for delete
            if st.session_state.get('confirm_admin_delete') == row['id']:
                st.warning(f"⚠️ Are you sure you want to delete admin user '{row['username']}'?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes, Delete", key=f"confirm_admin_yes_{row['id']}"):
                        # Remove admin user
                        admin_df = admin_df[admin_df['id'] != row['id']]
                        if safe_write_excel(admin_df, ADMIN_EXCEL_FILE):
                            st.session_state.confirm_admin_delete = None
                            st.success(f"✅ Admin user '{row['username']}' has been deleted!")
                            time.sleep(1)
                            st.rerun()
                with col_no:
                    if st.button("❌ No, Cancel", key=f"confirm_admin_no_{row['id']}"):
                        st.session_state.confirm_admin_delete = None
                        st.rerun()
            
            # Password reset section (collapsible for each user)
            with st.expander(f"🔐 Reset Password for {row['username']}"):
                col_pass1, col_pass2 = st.columns(2)
                with col_pass1:
                    new_pass = st.text_input(f"New Password", type="password", key=f"new_{row['id']}")
                with col_pass2:
                    confirm = st.text_input(f"Confirm Password", type="password", key=f"confirm_{row['id']}")
                
                if st.button(f"Update Password", key=f"update_{row['id']}"):
                    if new_pass and new_pass == confirm:
                        if len(new_pass) >= 6:
                            hashed = hash_password(new_pass)
                            admin_df.loc[admin_df['id'] == row['id'], 'password'] = hashed
                            if safe_write_excel(admin_df, ADMIN_EXCEL_FILE):
                                st.success(f"✅ Password for {row['username']} updated successfully!")
                                st.info(f"New password for {row['username']}: `{new_pass}`")
                                time.sleep(2)
                                st.rerun()
                        else:
                            st.error("Password must be at least 6 characters!")
                    else:
                        st.error("Passwords do not match or are empty!")
            
            st.markdown("---")
    
    # Add new admin user section
    st.subheader("➕ Add New Admin User")
    with st.expander("Create new admin account", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username *")
            new_email = st.text_input("Email *")
            new_fullname = st.text_input("Full Name *")
        with col2:
            new_password = st.text_input("Password *", type="password")
            confirm_password = st.text_input("Confirm Password *", type="password")
            new_role = st.selectbox("Role", ["admin", "super_admin"])
        
        if st.button("➕ Create Admin User", key="create_admin"):
            if new_username and new_email and new_fullname and new_password:
                if new_password == confirm_password:
                    if len(new_password) >= 6:
                        # Check if username exists
                        if new_username in admin_df['username'].values:
                            st.error("Username already exists!")
                        else:
                            new_id = admin_df['id'].max() + 1 if not admin_df.empty else 1
                            hashed = hash_password(new_password)
                            new_admin = pd.DataFrame([{
                                'id': new_id,
                                'username': new_username,
                                'password': hashed,
                                'email': new_email,
                                'full_name': new_fullname,
                                'role': new_role
                            }])
                            admin_df = pd.concat([admin_df, new_admin], ignore_index=True)
                            if safe_write_excel(admin_df, ADMIN_EXCEL_FILE):
                                st.success(f"✅ Admin user '{new_username}' created successfully!")
                                st.info(f"Login credentials:\nUsername: {new_username}\nPassword: {new_password}\nRole: {new_role}")
                                time.sleep(2)
                                st.rerun()
                    else:
                        st.error("Password must be at least 6 characters!")
                else:
                    st.error("Passwords do not match!")
            else:
                st.error("Please fill all required fields (*)!")
def download_all_photos_to_local_folder(df):
    """Download all profile photos to local folder"""
    count = download_all_photos_to_folder(df)
    if count > 0:
        st.success(f"✅ Downloaded {count} profile photos to '{PHOTOS_DOWNLOAD_FOLDER}' folder!")
    else:
        st.warning("No profile photos found to download.")

def download_all_signatures_to_local_folder(df):
    """Download all signatures to local folder"""
    count = download_all_signatures_to_folder(df)
    if count > 0:
        st.success(f"✅ Downloaded {count} signatures to '{SIGNATURES_DOWNLOAD_FOLDER}' folder!")
    else:
        st.warning("No signatures found to download.")

def bulk_remove_backgrounds(filtered_df):
    """
    Optimized batch processing with progress tracking and stop functionality
    """
    st.session_state.stop_processing = False
    st.session_state.processing_active = True
    
    to_process = filtered_df[(filtered_df['signature_bg_removed_path'] == '') & (filtered_df['signature_path'] != '')]
    
    if to_process.empty:
        st.info("All signatures in filtered results already have backgrounds removed!")
        st.session_state.processing_active = False
        return
    
    total = len(to_process)
    st.warning(f"⚠️ Processing {total} signatures from filtered results. Click 'Stop Processing' to cancel.")
    st.info("💡 Removing backgrounds while preserving all signature strokes...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed = 0
    failed = 0
    
    # Load dataframe once
    df_full = safe_read_excel(STAFF_EXCEL_FILE)
    
    for idx, (_, row) in enumerate(to_process.iterrows()):
        # Check if stop requested
        if st.session_state.stop_processing:
            status_text.text(f"🛑 Stopped by user. Processed {processed} of {total}")
            progress_bar.empty()
            st.session_state.processing_active = False
            st.warning(f"Processing stopped. {processed} completed, {failed} failed, {total - processed} remaining.")
            return
        
        status_text.text(f"Processing ({idx+1}/{total}): {row['full_name']}")
        progress_bar.progress((idx) / total)
        
        if is_valid_path(row['signature_path']):
            try:
                clean_path = process_signature_background(
                    row['signature_path'],
                    row['id'],
                    row['full_name']
                )
                
                if clean_path:
                    df_full.loc[df_full['id'] == row['id'], 'signature_bg_removed_path'] = clean_path
                    processed += 1
                else:
                    failed += 1
                    
                # Save periodically to preserve progress
                if (idx + 1) % 5 == 0 or (idx + 1) == total:
                    safe_write_excel(df_full, STAFF_EXCEL_FILE)
                    
            except Exception as e:
                failed += 1
                st.error(f"Error processing {row['full_name']}: {str(e)}")
        
        progress_bar.progress((idx + 1) / total)
    
    # Final save
    safe_write_excel(df_full, STAFF_EXCEL_FILE)
    progress_bar.progress(1.0)
    status_text.text(f"✅ Complete! Processed: {processed} signatures preserved, Failed: {failed}")
    st.session_state.processing_active = False
    st.success(f"Complete! {processed} signatures now have transparent backgrounds with preserved ink quality.")
    time.sleep(2)
    st.rerun()

def download_all_signatures_zip(df):
    """Download all signatures as ZIP"""
    zip_buffer = io.BytesIO()
    count = 0
    
    with st.spinner(f"Creating ZIP file..."):
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for _, row in df.iterrows():
                sig_path = row['signature_bg_removed_path'] if row['signature_bg_removed_path'] else row['signature_path']
                if is_valid_path(sig_path):
                    try:
                        with open(sig_path, 'rb') as f:
                            clean_name = clean_filename(row['full_name'])
                            if row['signature_bg_removed_path']:
                                filename = f"{clean_name}_signature_clean.png"
                            else:
                                filename = f"{clean_name}_signature.png"
                            zip_file.writestr(filename, f.read())
                            count += 1
                    except:
                        pass
    
    zip_buffer.seek(0)
    if count > 0:
        st.download_button(
            label=f"📥 Download {count} Signatures (ZIP)",
            data=zip_buffer,
            file_name=f"signatures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="download_all_zip"
        )
    else:
        st.warning("No signatures found to download.")

def download_clean_signatures_zip(df):
    """Download only clean signatures as ZIP"""
    zip_buffer = io.BytesIO()
    count = 0
    
    with st.spinner(f"Creating ZIP file..."):
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for _, row in df.iterrows():
                if is_valid_path(row['signature_bg_removed_path']):
                    try:
                        with open(row['signature_bg_removed_path'], 'rb') as f:
                            clean_name = clean_filename(row['full_name'])
                            filename = f"{clean_name}_signature_clean.png"
                            zip_file.writestr(filename, f.read())
                            count += 1
                    except:
                        pass
    
    zip_buffer.seek(0)
    if count > 0:
        st.download_button(
            label=f"📥 Download {count} Clean Signatures (ZIP)",
            data=zip_buffer,
            file_name=f"clean_signatures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="download_clean_zip"
        )
        st.success(f"✅ Downloaded {count} signatures with preserved quality!")
    else:
        st.warning("No clean signatures found to download.")

def download_all_photos_zip(df):
    """Download all profile photos as ZIP"""
    zip_buffer = io.BytesIO()
    count = 0
    
    with st.spinner(f"Creating ZIP file..."):
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for _, row in df.iterrows():
                if is_valid_path(row['image_path']):
                    try:
                        with open(row['image_path'], 'rb') as f:
                            clean_name = clean_filename(row['full_name'])
                            filename = f"{clean_name}_photo.png"
                            zip_file.writestr(filename, f.read())
                            count += 1
                    except:
                        pass
    
    zip_buffer.seek(0)
    if count > 0:
        st.download_button(
            label=f"📥 Download {count} Profile Photos (ZIP)",
            data=zip_buffer,
            file_name=f"profile_photos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            key="download_photos_zip"
        )
        st.success(f"✅ Packaged {count} profile photos!")
    else:
        st.warning("No profile photos found to download.")

def admin_all_staff():
    st.title("📋 All Staff Members")
    
    # Add Signature Remover Button at the top
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("✍️ Signature Background Remover", use_container_width=True, key="open_sig_remover"):
            st.session_state.show_signature_remover = True
            st.rerun()
    
    if st.session_state.show_signature_remover:
        signature_remover_app()
        return
    
    try:
        df = clean_database()
    except:
        df = safe_read_excel(STAFF_EXCEL_FILE)
    
    if df.empty:
        st.info("No staff members registered yet.")
        return
    
    df = df[df['full_name'].notna()]
    df = df[df['full_name'] != '']
    df = df.fillna('')
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Staff", len(df))
    col2.metric("Ministries", df['ministry'].nunique() if 'ministry' in df.columns else 0)
    col3.metric("Departments", df['department'].nunique() if 'department' in df.columns else 0)
    has_credentials = len(df[(df['username'] != '') & (df['password'] != '')])
    col4.metric("Has Credentials", has_credentials)
    clean_count = len(df[df['signature_bg_removed_path'] != ''])
    col5.metric("Clean Signatures", clean_count)
    photo_count = len(df[df['image_path'] != ''])
    col6.metric("Has Photos", photo_count)
    
    # Show current admin role
    st.info(f"Logged in as: **{st.session_state.user_role.upper()}** - {st.session_state.user_name}")
    
    st.markdown("---")
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_term = st.text_input("🔍 Wildcard Search (Name, Email, Phone, Username, Ministry, Department, Designation)", 
                                   key="staff_search_admin", 
                                   placeholder="Enter any search term...")
    with search_col2:
        if st.button("Clear Search", key="clear_search_btn"):
            st.session_state.staff_search_admin = ""
            st.rerun()
    
    filtered_df = search_staff(df, search_term)
    if search_term:
        st.info(f"Found {len(filtered_df)} matching staff members")
    
    st.markdown("---")
    st.subheader("Batch Operations on Filtered Results")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        if st.button("🖼️ Bulk Remove Backgrounds", type="primary", key="bulk_remove_btn"):
            bulk_remove_backgrounds(filtered_df)
    
    with col2:
        if st.button("🛑 Stop Processing", type="secondary", key="stop_processing_btn"):
            st.session_state.stop_processing = True
            st.warning("Stopping process... Please wait.")
    
    with col3:
        if st.button("📦 Download ALL Signatures (ZIP)", key="download_all_sig_btn"):
            download_all_signatures_zip(filtered_df)
    
    with col4:
        if st.button("📦 Download CLEAN Signatures (ZIP)", key="download_clean_sig_btn"):
            download_clean_signatures_zip(filtered_df)
    
    with col5:
        if st.button("📸 Download ALL Photos (ZIP)", key="download_photos_zip_btn"):
            download_all_photos_zip(filtered_df)
    
    with col6:
        if st.button("💾 Save to Local Folder", key="save_local_btn"):
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button("📸 Save Photos to Folder"):
                    download_all_photos_to_local_folder(filtered_df)
            with col_save2:
                if st.button("✍️ Save Signatures to Folder"):
                    download_all_signatures_to_local_folder(filtered_df)
    
    st.markdown("---")
    
    for idx, row in filtered_df.iterrows():
        if row['id'] == '' or pd.isna(row['id']):
            continue
        if not row['full_name']:
            continue
            
        staff_id = int(row['id']) if not pd.isna(row['id']) else idx
        
        with st.expander(f"👤 {row['full_name']} - {row['email']}"):
            if st.session_state.edit_mode and st.session_state.editing_staff_id == staff_id:
                st.subheader(f"✏️ Editing: {row['full_name']}")
                
                with st.form(key=f"edit_form_{staff_id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_username = st.text_input("Username", value=row['username'] if row['username'] else "")
                        new_password = st.text_input("Password", type="password", value="")
                        confirm_password = st.text_input("Confirm Password", type="password", value="")
                    with col2:
                        new_ministry = st.text_input("Ministry", value=row['ministry'] if row['ministry'] else "")
                        new_department = st.text_input("Department", value=row['department'] if row['department'] else "")
                        new_designation = st.text_input("Designation", value=row['designation'] if row['designation'] else "")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.form_submit_button("💾 Save Changes"):
                            df_full = safe_read_excel(STAFF_EXCEL_FILE)
                            df_full.loc[df_full['id'] == staff_id, 'username'] = new_username
                            if new_password:
                                if new_password == confirm_password:
                                    df_full.loc[df_full['id'] == staff_id, 'password'] = new_password
                                else:
                                    st.error("Passwords do not match!")
                                    return
                            df_full.loc[df_full['id'] == staff_id, 'ministry'] = new_ministry
                            df_full.loc[df_full['id'] == staff_id, 'department'] = new_department
                            df_full.loc[df_full['id'] == staff_id, 'designation'] = new_designation
                            df_full.loc[df_full['id'] == staff_id, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df_full.loc[df_full['id'] == staff_id, 'updated_by'] = st.session_state.user_name
                            
                            if safe_write_excel(df_full, STAFF_EXCEL_FILE):
                                st.success("Staff information updated successfully!")
                                st.session_state.edit_mode = False
                                st.session_state.editing_staff_id = None
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to save. Please close Excel file if open.")
                    
                    with col_btn2:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state.edit_mode = False
                            st.session_state.editing_staff_id = None
                            st.rerun()
            
            else:
                # View Mode
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**Email:** {row['email']}")
                    st.write(f"**Phone:** {row['phone_number']}")
                    st.write(f"**Ministry:** {row['ministry'] if row['ministry'] else 'N/A'}")
                    st.write(f"**Department:** {row['department'] if row['department'] else 'N/A'}")
                    st.write(f"**Designation:** {row['designation'] if row['designation'] else 'N/A'}")
                    st.write(f"**Username:** {row['username'] if row['username'] else '❌ Not set'}")
                    st.write(f"**Password:** {'✅ Set' if row['password'] else '❌ Not set'}")
                    st.write(f"**Signature Status:** {'✅ Background Removed' if row['signature_bg_removed_path'] else '⚠️ Original'}")
                    if row['registered_at'] and row['registered_at']:
                        st.write(f"**Registered:** {str(row['registered_at'])[:10]}")
                    if row['updated_at'] and row['updated_at']:
                        st.write(f"**Last Updated:** {str(row['updated_at'])[:10]} by {row['updated_by']}")
                
                with col2:
                    if is_valid_path(row['image_path']):
                        try:
                            with open(row['image_path'], 'rb') as f:
                                img = bytes_to_image(f.read())
                                circular_img = make_circular_image(img, size=(150, 150))
                                st.image(circular_img, caption=None, width=150)
                        except Exception as e:
                            st.info("📷 Photo error")
                    else:
                        st.info("📷 No photo")
                
                with col3:
                    sig_path = row['signature_bg_removed_path'] if row['signature_bg_removed_path'] else row['signature_path']
                    if is_valid_path(sig_path):
                        try:
                            with open(sig_path, 'rb') as f:
                                img = bytes_to_image(f.read())
                                circular_sig = make_circular_image(img, size=(150, 150))
                                st.image(circular_sig, caption=None, width=150)
                                if row['signature_bg_removed_path']:
                                    st.caption("✅ Clean (Preserved)")
                                else:
                                    st.caption("⚠️ Original")
                        except Exception as e:
                            st.info("✍️ Signature error")
                    else:
                        st.info("✍️ No signature")
                
                st.markdown("---")
                col_btn1, col_btn2, col_btn3, col_btn4, col_btn5, col_btn6 = st.columns(6)
                
                with col_btn1:
                    if st.button(f"✏️ Edit", key=f"edit_{staff_id}"):
                        st.session_state.edit_mode = True
                        st.session_state.editing_staff_id = staff_id
                        st.rerun()
                
                with col_btn2:
                    if not row['signature_bg_removed_path']:
                        if st.button(f"🖼️ Remove BG", key=f"remove_bg_{staff_id}"):
                            if is_valid_path(row['signature_path']):
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                status_text.text("Removing background while preserving signature...")
                                progress_bar.progress(0.3)
                                
                                with open(row['signature_path'], 'rb') as f:
                                    signature_bytes = f.read()
                                
                                progress_bar.progress(0.6)
                                clean_sig = remove_signature_background_preserve(signature_bytes)
                                
                                if clean_sig:
                                    progress_bar.progress(0.9)
                                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    clean_name = clean_filename(row['full_name'])
                                    clean_path = save_clean_signature_to_file(clean_sig, f"{clean_name}_{ts}.png")
                                    df_full = safe_read_excel(STAFF_EXCEL_FILE)
                                    df_full.loc[df_full['id'] == staff_id, 'signature_bg_removed_path'] = clean_path
                                    if safe_write_excel(df_full, STAFF_EXCEL_FILE):
                                        progress_bar.progress(1.0)
                                        status_text.text("Complete! Signature fully preserved.")
                                        time.sleep(0.5)
                                        progress_bar.empty()
                                        status_text.empty()
                                        st.success("Background removed successfully! Signature fully preserved.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("Failed to save. Please close Excel file.")
                                else:
                                    progress_bar.empty()
                                    status_text.empty()
                                    st.warning("Background removal failed.")
                    else:
                        st.success("✅ BG Removed")
                
                with col_btn3:
                    if row['signature_bg_removed_path'] and is_valid_path(row['signature_bg_removed_path']):
                        clean_name = clean_filename(row['full_name'])
                        with open(row['signature_bg_removed_path'], 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode()
                            href = f'<a href="data:image/png;base64,{b64}" download="{clean_name}_signature_clean.png">📥 Download Clean Sig</a>'
                            st.markdown(href, unsafe_allow_html=True)
                    elif row['signature_path'] and is_valid_path(row['signature_path']):
                        clean_name = clean_filename(row['full_name'])
                        with open(row['signature_path'], 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode()
                            href = f'<a href="data:image/png;base64,{b64}" download="{clean_name}_signature_original.png">📥 Download Original Sig</a>'
                            st.markdown(href, unsafe_allow_html=True)
                
                with col_btn4:
                    if is_valid_path(row['image_path']):
                        clean_name = clean_filename(row['full_name'])
                        with open(row['image_path'], 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode()
                            href = f'<a href="data:image/png;base64,{b64}" download="{clean_name}_photo.png">📸 Download Photo</a>'
                            st.markdown(href, unsafe_allow_html=True)
                
                with col_btn5:
                    if is_valid_path(row['image_path']):
                        clean_name = clean_filename(row['full_name'])
                        with open(row['image_path'], 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode()
                            href = f'<a href="data:image/png;base64,{b64}" download="{clean_name}_photo_rectangular.png">🖼️ Download Rectangular</a>'
                            st.markdown(href, unsafe_allow_html=True)
                
                with col_btn6:
                    # Delete button - ONLY visible to Super Admin
                    if st.session_state.user_role == 'super_admin':
                        delete_key = f"delete_btn_{staff_id}"
                        if st.button(f"🗑️ Delete Staff", key=delete_key):
                            st.session_state.confirm_delete = staff_id
                            st.rerun()
                        
                        # Show confirmation dialog
                        if st.session_state.confirm_delete == staff_id:
                            st.warning(f"⚠️ Are you sure you want to delete {row['full_name']}?")
                            col_confirm1, col_confirm2 = st.columns(2)
                            with col_confirm1:
                                if st.button("✅ Yes, Delete", key=f"confirm_yes_{staff_id}"):
                                    # Delete image files
                                    for path in [row['image_path'], row['signature_path'], row['signature_bg_removed_path']]:
                                        if is_valid_path(path):
                                            try:
                                                os.remove(path)
                                            except:
                                                pass
                                    # Remove from dataframe
                                    df_full = safe_read_excel(STAFF_EXCEL_FILE)
                                    df_full = df_full[df_full['id'] != staff_id]
                                    if safe_write_excel(df_full, STAFF_EXCEL_FILE):
                                        st.session_state.confirm_delete = None
                                        st.success(f"✅ Deleted {row['full_name']} successfully!")
                                        time.sleep(1)
                                        st.rerun()
                            with col_confirm2:
                                if st.button("❌ No, Cancel", key=f"confirm_no_{staff_id}"):
                                    st.session_state.confirm_delete = None
                                    st.rerun()
                    else:
                        st.info("🔒 Delete requires Super Admin role")


# ==================== MAIN ====================
def main():
    st.sidebar.title("Staff Management System")
    
    if st.session_state.logged_in:
        if st.session_state.user_type == "admin":
            # Display role in sidebar
            role_icon = "👑" if st.session_state.user_role == 'super_admin' else "🛡️"
            st.sidebar.write(f"{role_icon} **{st.session_state.user_name}** ({st.session_state.user_role})")
            st.sidebar.markdown("---")
            
            # Only show Admin Settings to Super Admin
            if st.session_state.user_role == 'super_admin':
                page = st.sidebar.radio("Navigation", ["All Staff", "Admin Settings"])
            else:
                page = st.sidebar.radio("Navigation", ["All Staff"])
            
            if page == "All Staff":
                admin_all_staff()
            elif page == "Admin Settings":
                admin_password_manager()
            
            st.sidebar.markdown("---")
            if st.sidebar.button("🚪 Logout", use_container_width=True, key="admin_logout"):
                for key in ['logged_in', 'user_type', 'user_name', 'stop_processing', 'processing_active', 'edit_mode', 'editing_staff_id', 'confirm_delete', 'show_signature_remover', 'user_role']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        
        elif st.session_state.user_type == "staff":
            staff_dashboard()
    
    else:
        choice = st.sidebar.radio("Select Option", 
                                 ["📝 New Registration", "🔐 Staff Login", "👨‍💼 Admin Login"])
        
        if choice == "📝 New Registration":
            end_user_registration()
        elif choice == "🔐 Staff Login":
            end_user_login()
        else:
            admin_login()

if __name__ == "__main__":
    os.makedirs("staff_images", exist_ok=True)
    os.makedirs("staff_signatures", exist_ok=True)
    os.makedirs("staff_signatures_clean", exist_ok=True)
    os.makedirs("downloads/photos", exist_ok=True)
    os.makedirs("downloads/signatures", exist_ok=True)
    main()