import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from flask import jsonify

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    symbl_rows = db.execute("SELECT DISTINCT(symbol) FROM transactions WHERE user_id=?", session["user_id"])
    sum = 0
    rows = []
    for symbl_row in symbl_rows:
        tmp = {}
        symbol = symbl_row["symbol"]
        shares = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id=? AND symbol=?",
                            session["user_id"], symbol)[0]["SUM(shares)"]
        data = lookup(symbol, True)
        total = data["price"] * shares
        sum += total
        tmp["symbol"] = symbol
        tmp["name"] = db.execute("SELECT name FROM companies WHERE symbol = ? LIMIT 1", symbol)[0]['name']
        tmp["shares"] = shares
        tmp["price"] = usd(data["price"])
        tmp["total"] = usd(total)
        rows.append(tmp)
    cash = db.execute("SELECT cash FROM users WHERE id=?;", session["user_id"])[0]["cash"]
    return render_template("index.html", rows=rows, cash=usd(cash), total=usd(sum+cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        name = request.form.get("name")
        if not name:
            return apology("Invalid Company Name", 400)
        shares = request.form.get("shares")
        if not shares:
            return apology("Invalid amount of shares", 400)
        shares = int(shares)
        data = lookup(name)
        print(data,"hi")
        if not data:
            return apology("Invalid Symbol", 400)
        if not shares or shares < 1:
            return apology("Enter a positive number of shares", 400)

        cash = db.execute("SELECT cash FROM users WHERE id=?;", session["user_id"])[0]["cash"]
        pay = data["price"] * shares
        if cash < pay:
            return apology("Cant aford", 400)
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                session["user_id"], data["symbol"], shares, data["price"])
        db.execute("UPDATE users SET cash=? WHERE id=?", cash-pay, session["user_id"])
        return redirect("/")


@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT * FROM transactions WHERE user_id=?;", session["user_id"])
    for row in rows:
        row["price"] = usd(row["price"])
        row["name"] = db.execute("SELECT name FROM companies WHERE symbol = ? LIMIT 1", row["symbol"])[0]['name']
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        name = request.form.get("name")
        data = lookup(name)
        if data:
            data["price"] = usd(data["price"])
            return render_template("quoted.html", data=data)
        else:
            return apology("Invalid Symbol", 400)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Ensure username was submitted
        username = request.form.get("username")
        password = request.form.get("password")
        cpassword = request.form.get("confirmation")
        if not username:
            return apology("must provide username", 400)
        usernames = f"{username}"
        lis = db.execute("SELECT 1 FROM users where username = ?;", usernames)
        if len(lis) != 0:
            return apology("username already exist, choose another one", 400)

        # Ensure password was submitted
        elif not password or not cpassword:
            return apology("must provide password and password confirmation", 400)
        elif not password == cpassword:
            return apology("passwords do not match")
        db.execute("INSERT INTO users(username, hash) VALUES(?, ?);", username, generate_password_hash(password))
        return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    symbols = []
    symbl_rows = db.execute("SELECT DISTINCT(symbol) FROM transactions WHERE user_id=?", session["user_id"])
    for row in symbl_rows:
        symbols.append(row["symbol"])
    if request.method == "GET":
        return render_template("sell.html", symbols=symbols)
    else:
        symbol = request.form.get("symbol")
        if not symbol or symbol not in symbols:
            return apology("Symbol is invalid", 400)
        shares = int(request.form.get("shares"))
        if not shares or shares < 1:
            return apology("Enter positive number of shares", 400)
        shares_own = int(db.execute("SELECT SUM(shares) FROM transactions WHERE user_id=? AND symbol=?",
                                    session["user_id"], symbol)[0]["SUM(shares)"])
        if shares_own < shares:
            return apology("does not own that many shares of the stock.", 400)
        data = lookup(symbol, True)
        cash = db.execute("SELECT cash FROM users WHERE id=?;", session["user_id"])[0]["cash"]
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                    session["user_id"], data["symbol"], shares*-1, data["price"])
        db.execute("UPDATE users SET cash=? WHERE id=?", cash+(int(data["price"])*shares), session["user_id"])
        return redirect("/")

@app.route("/search")
def search():
    companies = db.execute("SELECT name FROM companies WHERE name LIKE ?;", '%'+request.args.get('q')+'%')
    return jsonify(companies)
