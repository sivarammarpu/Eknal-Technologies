import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import hashlib
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Set a securely generated secret key for production
app.config['SECRET_KEY'] = os.urandom(24)  # For production, consider setting this securely
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    links = db.relationship('Link', backref='user', lazy=True)
    files = db.relationship('FileUpload', backref='user', lazy=True)

class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class FileUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Helpers
def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Custom decorator to require login for specific routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/admin')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    links = user.links
    files = user.files
    return render_template('dashboard.html', links=links, files=files)

import validators

@app.route('/add-link', methods=['GET', 'POST'])
@login_required
def add_link():
    if request.method == 'POST':
        title = request.form['title']
        url_link = request.form['url']

        # Check for empty fields
        if not title or not url_link:
            flash('Please provide both title and link.', 'danger')
            return redirect(url_for('add_link'))

        # Validate URL format
        if not validators.url(url_link):
            flash('Please provide a valid URL (e.g., https://example.com).', 'danger')
            return redirect(url_for('add_link'))

        new_link = Link(title=title, url=url_link, user_id=session['user_id'])
        db.session.add(new_link)
        db.session.commit()
        flash('Link added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_link.html')

@app.route('/add-file', methods=['GET', 'POST'])
@login_required
def add_file():
    if request.method == 'POST':
        title = request.form['title']
        file = request.files.get('file')

        if not title or not file:
            flash('Please provide both title and file.', 'danger')
            return redirect(url_for('add_file'))

        if not allowed_file(file.filename):
            flash(f'File type not allowed. Allowed types: {ALLOWED_EXTENSIONS}', 'danger')
            return redirect(url_for('add_file'))

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Avoid filename collisions by appending number if needed
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter += 1

        file.save(filepath)

        new_file = FileUpload(title=title, filename=filename, user_id=session['user_id'])
        db.session.add(new_file)
        db.session.commit()
        flash('File uploaded successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_file.html')

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    file_record = FileUpload.query.get_or_404(file_id)
    if file_record.user_id != session['user_id']:
        flash('You do not have permission to download this file.', 'danger')
        return redirect(url_for('dashboard'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], file_record.filename, as_attachment=True)

@app.route('/edit-link/<int:link_id>', methods=['GET', 'POST'])
@login_required
def edit_link(link_id):
    link = Link.query.get_or_404(link_id)
    
    # Ensure the logged-in user owns this link
    if link.user_id != session['user_id']:
        flash('You do not have permission to edit this link.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        link.title = request.form['title']
        link.url = request.form['url']
        db.session.commit()
        flash('Link updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_link.html', link=link)

@app.route('/edit-file/<int:file_id>', methods=['GET', 'POST'])
@login_required
def edit_file(file_id):
    file_record = FileUpload.query.get_or_404(file_id)

    # Ensure the logged-in user owns this file
    if file_record.user_id != session['user_id']:
        flash('You do not have permission to edit this file.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        file_record.title = request.form['title']
        db.session.commit()
        flash('File updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_file.html', file=file_record)

@app.route('/delete-link/<int:link_id>')
@login_required
def delete_link(link_id):
    link = Link.query.get_or_404(link_id)
    if link.user_id != session['user_id']:
        flash('You cannot delete this link.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(link)
    db.session.commit()
    flash('Link deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-file/<int:file_id>')
@login_required
def delete_file(file_id):
    file = FileUpload.query.get_or_404(file_id)
    if file.user_id != session['user_id']:
        flash('You cannot delete this file.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Delete file from server
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.session.delete(file)
    db.session.commit()
    flash('File deleted successfully.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def resources():
    """Public Linktree-style view for a specific user."""
    user = User.query.first()
    links = user.links
    files = user.files
    return render_template('resources.html', links=links, files=files, username=user.username)

from flask import send_from_directory, abort

# 🟢 Preview route — for iframe viewing
@app.route('/preview/<int:file_id>')
def preview_file(file_id):
    file_record = FileUpload.query.get_or_404(file_id)
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], file_record.filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)

# 🔵 Download route — for download button
@app.route('/public-download/<int:file_id>')
def public_download(file_id):
    file_record = FileUpload.query.get_or_404(file_id)
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], file_record.filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

import hashlib
print(hasattr(hashlib, 'scrypt'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    debug_mode = True if os.getenv('FLASK_DEBUG', 'False').lower() == 'true' else False
    app.run(debug=debug_mode, port=7800, host='0.0.0.0')
