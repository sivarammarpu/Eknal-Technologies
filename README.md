<p align="center">
  <img src="static/eknal_link.png" alt="Eknal Link Logo" height="60">
</p>

<h1 align="center">Eknal Link</h1>

<p align="center">
  A professional resource-sharing and team management platform built for Eknal Technologies.
  <br/>
  Share curated links, files, and meet the team — all in one place.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Flask-3.0-black?logo=flask">
  <img src="https://img.shields.io/badge/SQLite-Database-lightgrey?logo=sqlite">
  <img src="https://img.shields.io/badge/Redis-OTP%20Storage-red?logo=redis">
  <img src="https://img.shields.io/badge/TailwindCSS-UI-38bdf8?logo=tailwindcss">
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Pages & Routes](#pages--routes)
- [Security](#security)
- [License & Copyright](#license--copyright)

---

## Overview

**Eknal Link** is a full-stack Flask web application developed as part of the Eknal Technologies internship program. It provides:

- A **public-facing portal** where users can browse curated links and files, and view the team's collaborators.
- A **secure admin dashboard** for managing all content (links, files, collaborators).
- A **self-service OTP edit flow** allowing collaborators to update their own profiles via email verification.

---

## Features

### Public
- 🔗 **Resources Page** — Browse links and downloadable files with live instant search
- 👥 **Team Page** — Meet the project collaborators with avatar cards and resume links

### Admin
- 🔐 **Secure Login** — Password-hashed admin authentication with 30-minute session timeout
- 📊 **Dashboard** — Manage links (with click counter), files, and collaborators in one place
- ➕ **Add / Edit / Delete** — Full CRUD operations for links, files, and collaborators
- 📁 **File Uploads** — Upload files up to 16 MB with automatic duplicate filename handling

### Collaborator Self-Service
- 📧 **OTP Verification** — Collaborators receive a 6-digit code to their registered email
- ✏️ **Edit Profile** — Update name, resume URL, and role after identity verification

### Developer
- ⚡ **Click Tracking** — Every link click is counted and displayed on the dashboard
- 🛡️ **CSRF Protection** — All state-changing forms are CSRF-protected
- 🚫 **Rate Limiting** — OTP requests are limited to 3 per 10 minutes
- ❌ **Custom Error Pages** — Branded 404 and 500 error pages
- ✅ **Input Validation** — URL format, email format, and field presence validated on every form

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.0 |
| Database | SQLite via Flask-SQLAlchemy |
| OTP Storage | Redis |
| Email | SMTP (Zoho Mail) via `smtplib` |
| Security | Flask-WTF (CSRF), Flask-Limiter (rate limiting), Werkzeug (password hashing) |
| UI | Tailwind CSS (CDN), Inter font (Google Fonts) |
| Config | python-dotenv |

---

## Project Structure

```
eknal_link/
├── app.py                  # Main Flask application (routes, models, helpers)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (NOT committed — see below)
├── .gitignore
│
├── static/
│   └── eknal_link.png      # Logo asset
│
├── templates/
│   ├── resources.html      # Public resources page (with search)
│   ├── collaborators.html  # Public team page
│   ├── dashboard.html      # Admin dashboard
│   ├── admin_login.html    # Admin login form
│   ├── add_link.html       # Add link form
│   ├── edit_link.html      # Edit link form
│   ├── add_file.html       # Upload file form
│   ├── edit_file.html      # Edit file title form
│   ├── add_collaborator.html
│   ├── edit_collaborator.html
│   ├── request_edit.html   # OTP request form (collaborator self-edit)
│   ├── verify_otp.html     # OTP verification form
│   ├── self_edit.html      # Collaborator profile edit form
│   ├── 404.html            # Custom 404 error page
│   └── 500.html            # Custom 500 error page
│
└── uploads/                # Uploaded files (NOT committed)
```

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Redis server running locally (or remote)
- A working SMTP email account (Zoho, Gmail App Password, etc.)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/sivarammarpu/Eknal-Technologies.git
cd Eknal-Technologies

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment variables
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
# Then edit .env with your own values
```

---

## Environment Variables

Create a `.env` file in the project root (never commit this file):

```env
# Flask
SECRET_KEY=your-very-secret-key-here

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=         # Leave blank to use default dev password (admin123)

# Email (SMTP)
EMAIL_USER=your@email.com
EMAIL_PASS=your-email-password
EMAIL_FROM=your@email.com

# Redis
REDIS_SERVER_NUMBER=localhost
REDIS_PORT_NUMBER=6379
REDIS_PASSWORD=              # Leave blank if no password
```

> ⚠️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

To generate a secure `SECRET_KEY`, run:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Running the App

```bash
python app.py
```

The app will be available at **http://127.0.0.1:5000**

> **Admin login:** Navigate to `/admin-login` and sign in with your configured credentials.  
> Default development credentials: username `admin`, password `admin123`.

---

## Pages & Routes

| Route | Access | Description |
|---|---|---|
| `/` | Public | Redirects to `/resources` |
| `/resources` | Public | Browse links and files; instant search |
| `/collaborators` | Public | View team member cards |
| `/open/<id>` | Public | Click-tracking redirect for links |
| `/download/<id>` | Public | Download an uploaded file |
| `/preview/<id>` | Public | Preview an uploaded file in browser |
| `/request-edit` | Public | Collaborator OTP request (rate limited) |
| `/verify-otp` | Public | OTP verification |
| `/self-edit` | Public (verified) | Collaborator profile edit |
| `/admin-login` | Public | Admin authentication |
| `/admin-logout` | Admin | Logout and clear session |
| `/dashboard` | Admin | Main control panel |
| `/add-link` | Admin | Create a new link |
| `/edit-link/<id>` | Admin | Edit an existing link |
| `/delete-link/<id>` | Admin (POST) | Delete a link |
| `/add-file` | Admin | Upload a file |
| `/edit-file/<id>` | Admin | Edit a file's display title |
| `/delete-file/<id>` | Admin (POST) | Delete a file |
| `/add-collaborator` | Admin | Add a new collaborator |
| `/edit-collaborator/<id>` | Admin | Edit collaborator details |
| `/delete-collaborator/<id>` | Admin (POST) | Remove a collaborator |

---

## Security

This application implements the following security best practices:

- 🔐 **Password hashing** — Admin password stored as a Werkzeug `pbkdf2:sha256` hash
- 🛡️ **CSRF protection** — All forms include a signed CSRF token via Flask-WTF
- ⏱️ **Rate limiting** — OTP endpoint limited to 3 requests per 10 minutes (Flask-Limiter)
- ⏰ **Session expiry** — Admin sessions automatically expire after 30 minutes of inactivity
- 📏 **File size limit** — Uploads capped at 16 MB
- ✅ **Input validation** — URL format, email format, and field presence verified server-side
- 🔗 **External link safety** — All `target="_blank"` links include `rel="noopener noreferrer"`
- 🚫 **No secrets in code** — All credentials and keys loaded via environment variables

---

## License & Copyright

```
Copyright © 2026 Siva Ram Marpu. All rights reserved.

This project and all its contents — including source code, templates,
design assets, and documentation — are the exclusive intellectual property
of Siva Ram Marpu.

Unauthorized copying, modification, distribution, public display,
or commercial use of any part of this project, in whole or in part,
is strictly prohibited without the express written permission of the owner.

No part of this repository may be reproduced or transmitted in any form
or by any means, electronic or mechanical, without prior written permission.
```

---

