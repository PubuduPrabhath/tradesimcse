import os
from cs50 import SQL
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps

db = SQL("sqlite:///finance.db")

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(name, is_symbol=False):
    """Look up quote for symbol."""

    # Contact API
    try:
        #api_key = os.environ.get("API_KEY")
        url = f"https://www.cse.lk/api/homeCompanyData"
        if not  is_symbol:
            symbol = db.execute("SELECT symbol FROM companies WHERE name = ? LIMIT 1", name)[0]['symbol']
            data = {"symbol": symbol}
        else:
            data = {"symbol": name}
        response = requests.post(url, data)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": name,
            "price": float(quote["price"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as LKR."""
    return f"LKR {value:,.2f}"
