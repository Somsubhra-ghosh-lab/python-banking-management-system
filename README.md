# Python Banking Management System

A learning/college project built with Python, Flask, SQLite, HTML, CSS, and a little JavaScript.

## Features
- User registration and login
- Password hashing using Werkzeug
- Auto-created demo account number
- Dashboard with balance and recent activity
- Deposit and withdrawal flows
- Account-to-account transfers
- Transaction history
- SQLite database and basic relational constraints
- Input validation and transactional transfer updates

## Requirements
- Python 3.10+
- pip

## Run locally
1. Extract the ZIP and open a terminal in this folder.
2. Create and activate a virtual environment (recommended).
   - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
   - Windows: `py -m venv .venv && .venv\Scripts\activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start the app: `python app.py`
5. Open `http://127.0.0.1:5000` in your browser.
6. Register a user. To test transfers, register a second user in another browser/incognito window and use their account number.

## Project structure
```
python_banking_management_system/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── transaction_form.html
│   └── transactions.html
└── static/
    └── style.css
```

## Important limitations
This is a demo/educational project, not production banking software. Do not use real money, real customer information, or real credentials. Before any public deployment, add CSRF protection, rate limiting, secure production secret management, HTTPS, audit/security review, stronger authorization controls, backups, and appropriate regulatory/compliance safeguards. Use a production WSGI server instead of Flask's development server.
