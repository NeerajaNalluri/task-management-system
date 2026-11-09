"""Change a user's password from the terminal (useful if you're locked out).

Usage:  python reset_password.py admin
        python reset_password.py user

The new password is typed hidden and is never saved in plain text.
"""

import sys
from getpass import getpass

from app import app
from extensions import db
from models import User

if len(sys.argv) != 2:
    print("Usage: python reset_password.py <username>")
    sys.exit(1)

username = sys.argv[1]

with app.app_context():
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"No user called '{username}'.")
        sys.exit(1)

    password = getpass(f"New password for {username}: ")
    if len(password) < 8:
        print("Password must be at least 8 characters. Nothing changed.")
        sys.exit(1)
    if getpass("Type it again: ") != password:
        print("Passwords don't match. Nothing changed.")
        sys.exit(1)

    user.set_password(password)  # scrambles it before saving
    db.session.commit()
    print(f"Password for '{username}' changed.")
