import os
import re
import redis
import smtplib
import random
from datetime import timedelta
from email.message import EmailMessage
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, session, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# ---------------- EMAIL / REDIS CONFIG ----------------
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")

REDIS_HOST     = os.getenv("REDIS_SERVER_NUMBER", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT_NUMBER", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# ---------------- APP ----------------
app = Flask(__name__)
app.config["SECRET_KEY"]                  = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config["SQLALCHEMY_DATABASE_URI"]     = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_ENABLED"]            = True
app.config["MAX_CONTENT_LENGTH"]          = 16 * 1024 * 1024   # 16 MB upload limit
app.config["PERMANENT_SESSION_LIFETIME"]  = timedelta(minutes=30)

UPLOAD_FOLDER     = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "docx", "xlsx", "pptx", "zip"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db   = SQLAlchemy(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# ---------------- ADMIN CREDENTIALS ----------------
ADMIN_USERNAME    = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash("admin123")   # dev fallback only
)

# ---------------- MODELS ----------------
class Link(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(120), nullable=False)
    url         = db.Column(db.String(500), nullable=False)
    clicks      = db.Column(db.Integer, default=0, nullable=False)
    created_at  = db.Column(db.DateTime, default=db.func.now())

class FileUpload(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(120), nullable=False)
    filename    = db.Column(db.String(300), nullable=False)
    created_at  = db.Column(db.DateTime, default=db.func.now())

class Collaborator(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(120), nullable=False)
    email        = db.Column(db.String(120), nullable=False, unique=True)
    resume_url   = db.Column(db.String(500), nullable=False)
    contribution = db.Column(db.String(300), nullable=False)
    joined_at    = db.Column(db.DateTime, default=db.func.now())

# ---------------- HELPERS ----------------
def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

def is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://[^\s]+$", url))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required. Please log in.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ---------------- OTP HELPERS ----------------
def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def save_otp(email: str, otp: str):
    redis_client.setex(f"otp:{email}", 300, otp)

def get_otp(email: str):
    return redis_client.get(f"otp:{email}")

def delete_otp(email: str):
    redis_client.delete(f"otp:{email}")

# ---------------- EMAIL ----------------
def send_email(to: str, otp: str):
    msg = EmailMessage()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = to
    msg["Subject"] = "Eknal Technologies – Email Verification Code"
    msg.add_alternative(f"""
<html>
<body style="background-color:#f4f6fb;font-family:Arial,sans-serif;padding:30px;">
  <div style="max-width:480px;margin:auto;background:#fff;border-radius:12px;
              padding:30px;box-shadow:0 4px 12px rgba(0,0,0,.08);text-align:center;">
    <img src="https://i.ibb.co/39ZNH1W0/eknal-link.png"
         style="height:50px;margin-bottom:20px;" alt="Eknal Link"/>
    <h2 style="color:#4f46e5;margin-bottom:10px;">OTP Verification</h2>
    <p style="color:#555;font-size:15px;">
      We received a request to update your collaborator profile.
    </p>
    <p style="color:#555;font-size:15px;">Use the verification code below:</p>
    <div style="font-size:28px;font-weight:bold;letter-spacing:6px;
                background:#f0f2ff;padding:15px;border-radius:8px;
                margin:20px 0;color:#111;">
      {otp}
    </div>
    <p style="color:#777;font-size:14px;">This code is valid for 5 minutes.</p>
    <p style="color:#999;font-size:13px;">
      If you did not request this, you can safely ignore this email.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:25px 0;">
    <p style="font-size:13px;color:#666;">&copy; Eknal Technologies</p>
  </div>
</body>
</html>
""", subtype="html")

    try:
        server = smtplib.SMTP("smtp.zoho.in", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
    except smtplib.SMTPException as exc:
        app.logger.error("SMTP error sending OTP to %s: %s", to, exc)
        raise RuntimeError("Email delivery failed. Please try again later.")

# ---------------- ERROR HANDLERS ----------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

@app.errorhandler(413)
def file_too_large(e):
    flash("File too large. Maximum allowed size is 16 MB.", "danger")
    return redirect(url_for("add_file"))

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect(url_for("resources"))

# ---------------- ADMIN AUTH ----------------
@app.route("/admin-entry")
def admin_entry():
    if session.get("is_admin"):
        session.pop("is_admin", None)
        flash("Logged out successfully.", "info")
        return redirect(url_for("resources"))
    return redirect(url_for("admin_login"))

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if (
            username == ADMIN_USERNAME and
            check_password_hash(ADMIN_PASSWORD_HASH, password)
        ):
            session.permanent = True
            session["is_admin"] = True
            flash("Login successful. Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")

    return render_template("admin_login.html")

@app.route("/admin-logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("resources"))

# ---------------- PUBLIC RESOURCES ----------------
@app.route("/resources")
def resources():
    links = Link.query.order_by(Link.id.desc()).all()
    files = FileUpload.query.order_by(FileUpload.id.desc()).all()
    return render_template("resources.html", links=links, files=files)

# Link click tracker (increments counter then redirects)
@app.route("/open/<int:id>")
def open_link(id):
    link = Link.query.get_or_404(id)
    link.clicks += 1
    db.session.commit()
    return redirect(link.url)

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@admin_required
def dashboard():
    links         = Link.query.order_by(Link.id.desc()).all()
    files         = FileUpload.query.order_by(FileUpload.id.desc()).all()
    collaborators = Collaborator.query.order_by(Collaborator.id.desc()).all()
    return render_template(
        "dashboard.html",
        links=links,
        files=files,
        collaborators=collaborators
    )

# ---------------- LINKS ----------------
@app.route("/add-link", methods=["GET", "POST"])
@admin_required
def add_link():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url   = request.form.get("url", "").strip()

        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("add_link"))

        if not is_valid_url(url):
            flash("Please enter a valid URL starting with http:// or https://", "danger")
            return redirect(url_for("add_link"))

        db.session.add(Link(title=title, url=url))
        db.session.commit()
        flash("Link added successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_link.html")

@app.route("/edit-link/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_link(id):
    link = Link.query.get_or_404(id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url   = request.form.get("url", "").strip()

        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("edit_link", id=id))

        if not is_valid_url(url):
            flash("Please enter a valid URL.", "danger")
            return redirect(url_for("edit_link", id=id))

        link.title = title
        link.url   = url
        db.session.commit()
        flash("Link updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_link.html", link=link)

@app.route("/delete-link/<int:id>", methods=["POST"])
@admin_required
def delete_link(id):
    link = Link.query.get_or_404(id)
    db.session.delete(link)
    db.session.commit()
    flash("Link deleted.", "success")
    return redirect(url_for("dashboard"))

# ---------------- FILES ----------------
@app.route("/add-file", methods=["GET", "POST"])
@admin_required
def add_file():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        file  = request.files.get("file")

        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("add_file"))

        if not file or file.filename == "":
            flash("Please select a file to upload.", "danger")
            return redirect(url_for("add_file"))

        if not allowed_file(file.filename):
            flash(
                f"File type not allowed. Permitted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                "danger"
            )
            return redirect(url_for("add_file"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Avoid overwriting existing files
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            counter += 1

        file.save(filepath)
        db.session.add(FileUpload(title=title, filename=filename))
        db.session.commit()
        flash("File uploaded successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_file.html")

@app.route("/edit-file/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_file(id):
    upload = FileUpload.query.get_or_404(id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("edit_file", id=id))
        upload.title = title
        db.session.commit()
        flash("File title updated.", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_file.html", file=upload)

@app.route("/download/<int:id>")
def download(id):
    f = FileUpload.query.get_or_404(id)
    return send_from_directory(UPLOAD_FOLDER, f.filename, as_attachment=True)

@app.route("/preview/<int:id>")
def preview_file(id):
    f = FileUpload.query.get_or_404(id)
    return send_from_directory(app.config["UPLOAD_FOLDER"], f.filename, as_attachment=False)

@app.route("/delete-file/<int:id>", methods=["POST"])
@admin_required
def delete_file(id):
    f    = FileUpload.query.get_or_404(id)
    path = os.path.join(UPLOAD_FOLDER, f.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(f)
    db.session.commit()
    flash("File deleted.", "success")
    return redirect(url_for("dashboard"))

# ---------------- COLLABORATORS ----------------
@app.route("/collaborators")
def collaborators():
    people = Collaborator.query.order_by(Collaborator.id.asc()).all()
    return render_template("collaborators.html", people=people)

@app.route("/add-collaborator", methods=["GET", "POST"])
@admin_required
def add_collaborator():
    if request.method == "POST":
        name         = request.form.get("name", "").strip()
        email        = request.form.get("email", "").strip()
        resume_url   = request.form.get("resume", "").strip()
        contribution = request.form.get("contribution", "").strip()

        if not all([name, email, resume_url, contribution]):
            flash("All fields are required.", "danger")
            return redirect(url_for("add_collaborator"))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("add_collaborator"))

        if Collaborator.query.filter_by(email=email).first():
            flash("A collaborator with this email already exists.", "danger")
            return redirect(url_for("add_collaborator"))

        db.session.add(Collaborator(
            name=name,
            email=email,
            resume_url=resume_url,
            contribution=contribution
        ))
        db.session.commit()
        flash("Collaborator added successfully.", "success")
        return redirect(url_for("collaborators"))

    return render_template("add_collaborator.html")

@app.route("/edit-collaborator/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_collaborator(id):
    c = Collaborator.query.get_or_404(id)

    if request.method == "POST":
        name         = request.form.get("name", "").strip()
        email        = request.form.get("email", "").strip()
        resume_url   = request.form.get("resume", "").strip()
        contribution = request.form.get("contribution", "").strip()

        if not all([name, email, resume_url, contribution]):
            flash("All fields are required.", "danger")
            return redirect(url_for("edit_collaborator", id=id))

        # check email uniqueness (exclude self)
        existing = Collaborator.query.filter_by(email=email).first()
        if existing and existing.id != id:
            flash("Another collaborator is already using this email.", "danger")
            return redirect(url_for("edit_collaborator", id=id))

        c.name         = name
        c.email        = email
        c.resume_url   = resume_url
        c.contribution = contribution
        db.session.commit()
        flash("Collaborator updated successfully.", "success")
        return redirect(url_for("collaborators"))

    return render_template("edit_collaborator.html", collaborator=c)

@app.route("/delete-collaborator/<int:id>", methods=["POST"])
@admin_required
def delete_collaborator(id):
    c = Collaborator.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Collaborator removed.", "success")
    return redirect(url_for("collaborators"))

# ---------------- OTP / SELF-EDIT FLOW ----------------
@app.route("/request-edit", methods=["GET", "POST"])
@limiter.limit("3 per 10 minutes")
def request_edit():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for("request_edit"))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("request_edit"))

        collaborator = Collaborator.query.filter_by(email=email).first()
        if not collaborator:
            flash("No collaborator found with this email.", "danger")
            return redirect(url_for("request_edit"))

        otp = generate_otp()
        save_otp(email, otp)

        try:
            send_email(email, otp)
        except RuntimeError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("request_edit"))

        session["otp_email"] = email
        flash("Verification code sent! Check your inbox.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("request_edit.html")

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form.get("otp", "").strip()
        email    = session.get("otp_email")

        if not email:
            flash("Session expired. Please start again.", "danger")
            return redirect(url_for("request_edit"))

        saved_otp = get_otp(email)
        if saved_otp is None:
            flash("OTP has expired. Please request a new one.", "danger")
            return redirect(url_for("request_edit"))

        if user_otp == saved_otp:
            delete_otp(email)
            session["verified_email"] = email
            flash("Identity verified. You may now update your profile.", "success")
            return redirect(url_for("self_edit_collaborator"))

        flash("Incorrect OTP. Please try again.", "danger")

    return render_template("verify_otp.html")

@app.route("/self-edit", methods=["GET", "POST"])
def self_edit_collaborator():
    email = session.get("verified_email")

    if not email:
        flash("Unauthorized access. Please verify your identity first.", "danger")
        return redirect(url_for("request_edit"))

    collaborator = Collaborator.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        name         = request.form.get("name", "").strip()
        resume_url   = request.form.get("resume", "").strip()
        contribution = request.form.get("contribution", "").strip()

        if not all([name, resume_url, contribution]):
            flash("All fields are required.", "danger")
            return redirect(url_for("self_edit_collaborator"))

        collaborator.name         = name
        collaborator.resume_url   = resume_url
        collaborator.contribution = contribution
        db.session.commit()

        session.pop("verified_email", None)
        session.pop("otp_email", None)

        flash("Your profile has been updated successfully.", "success")
        return redirect(url_for("collaborators"))

    return render_template("self_edit.html", collaborator=collaborator)

# ---------------- RUN ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
