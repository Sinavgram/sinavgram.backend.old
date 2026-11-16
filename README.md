# Sınavgram Backend (Legacy)

**Sınavgram** is an educational platform designed to help students prepare for exams through a question-based learning environment. This repository contains an older backend implementation of the platform, built with Python and Flask.

> **Note:** This is an archived/legacy backend implementation. It is preserved for reference and development history purposes and may not represent the current architecture of Sınavgram.

## Overview

The backend provides the core infrastructure for the Sınavgram platform, including user authentication, course and question management, community features, administrative tools, and AI-related functionality.

The application follows a modular architecture using Flask Blueprints to separate different functional areas.

## Features

### User Management & Authentication
- User registration and login.
- Secure password hashing.
- Email verification.
- Password reset functionality.
- JWT-based token handling.
- User profile and avatar management.
- Session and account security mechanisms.
- Login notification and session invalidation support.

### Educational System
- Course and subtopic management.
- Multiple-choice question system (A–E).
- Question submission by users.
- Question approval and moderation workflow.
- Question images and supporting PDF files.
- Answer tracking and evaluation.
- User scoring and points system.

### Community Features
- Question liking and bookmarking.
- Question reporting.
- User-generated questions.
- Community-oriented interactions.

### Administration
- Dedicated administrative authentication.
- Administrative dashboard.
- Question moderation.
- User management.
- Report management.
- IP-based administrative access restrictions.
- Administrative session management.

### Premium & Payments
- Premium subscription support.
- Monthly and yearly subscription plans.
- Subscription expiration tracking.
- Payment transaction records.
- Premium-only question support.

### AI Integration
- Dedicated AI Blueprint.
- Google Gemini API configuration.

### Email & External Services
- SMTP-based email functionality.
- Google API client integration.
- Google authentication support.
- Cross-Origin Resource Sharing (CORS) configuration.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Flask | Web application framework |
| Flask-SQLAlchemy | Database integration |
| SQLAlchemy | ORM |
| PostgreSQL | Relational database |
| Flask-Migrate | Database migration support |
| Flask-JWT-Extended | JWT authentication |
| PyJWT | Token generation and validation |
| Flask-Mail | Email functionality |
| Flask-CORS | Cross-origin resource sharing |
| Gunicorn | WSGI application server |
| Google API Client | Google service integration |

## Project Structure

```text
sinavgram.backend.old/
│
├── blueprints/
│   ├── auth_bp.py
│   ├── main_bp.py
│   ├── courses_bp.py
│   ├── questions_bp.py
│   ├── user_bp.py
│   ├── admin_panel_bp.py
│   ├── community_bp.py
│   ├── legal_bp.py
│   └── ai_bp.py
│
├── static/
│   └── uploads/
│
├── templates/
│
├── app.py
├── commands.py
├── config.py
├── decorators.py
├── extensions.py
├── models.py
├── utils.py
├── admin_ip_manager.py
│
├── requirements.txt
└── .gitignore
```

### Architecture

The application uses Flask's Application Factory pattern.

Each major feature is implemented as an independent Blueprint, while shared extensions and database models are managed centrally.

This structure helps separate business logic, authentication, database operations, and administrative functionality.

## Installation

### Prerequisites

- Python
- PostgreSQL
- pip
- Git

### 1. Clone the repository

```bash
git clone https://github.com/mehmetalper04/sinavgram.backend.old.git

cd sinavgram.backend.old
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows**
```bash
venv\Scripts\activate
```

**Linux / macOS**
```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database:

```sql
CREATE DATABASE sinavgram;
```

Configure the database connection using the `DATABASE_URL` environment variable.

Example:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/sinavgram
```

### 5. Configure application settings

The application requires several configuration values depending on the enabled features.

Important settings include:

- `SECRET_KEY`
- `DATABASE_URL`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `CORS_ALLOWED_ORIGINS`
- `API_BASE_URL`
- Google API credentials
- Gemini API credentials

**Security warning:** Review `config.py` before running the application. Replace hardcoded fallback credentials and secrets with secure configuration values. Do not expose production credentials in source control.

### 6. Run the application

For local development:

```bash
flask --app app run --debug
```

The development server will normally be available at:

```text
http://127.0.0.1:5000
```

For production environments, a WSGI server such as Gunicorn can be used:

```bash
gunicorn app:app
```

## Database

Sınavgram uses PostgreSQL as its primary relational database.

The data model includes entities such as:

- Users
- Courses
- Subtopics
- Questions
- User Answers
- Question Reports
- Payments
- Mailing List

SQLAlchemy handles database relationships and ORM operations.

## Development Notes

This repository represents an earlier implementation of the Sınavgram backend.

Some dependencies, configuration values, and architectural decisions may be outdated. Additional configuration or adjustments may be necessary depending on the runtime environment.

The `requirements.txt` file also contains some system administration commands alongside Python dependencies. These commands are not pip packages and should be handled separately when setting up the environment.

## License

No license has been specified for this repository. Please contact the repository owner before redistributing or using the source code in other projects.

## Author

**Mehmet Alper Kocaoğlu**

GitHub: [@mehmetalper04](https://github.com/mehmetalper04)

Repository: [sinavgram.backend.old](https://github.com/sinavgram/sinavgram.backend.old)

---

*Built as part of the Sınavgram educational platform project.*
