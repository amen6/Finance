import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    @app.route("/")
@login_required
def index():

    cash = db.execute('SELECT cash FROM users WHERE id = :user',user=session["user_id"])[0]['cash']
    stocks = db.execute('SELECT * FROM purchase WHERE user_id = :user',user=session["user_id"])
    final_total = cash
    if not stocks:
        return apology('sorry you have no stocks')

    for stock in stocks:

        price = lookup(stock['symbol'])['price']
        total = price * int(stock['shares'])

        stock.update({'price': price, 'total': total})
        final_total += total


    return render_template('index.html', cash=cash, stocks=stocks, price=price, total=total, final_total=final_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        if not request.form.get('symbol'):
            return apology('you should precise valid stock', 403)

        if not request.form.get('shares') or int(request.form.get('shares')) <= 0 :
            return apology('you should precise a positive share number', 403)

        shares = request.form.get('shares')
        symbol = lookup(request.form.get('symbol'))['symbol']

        cash = db.execute("SELECT cash FROM users WHERE id = :user",
                          user=session["user_id"])[0]['cash']

        price_before = lookup(request.form.get('symbol'))['price']
        cash_after = cash - float(price_before * float(shares))
        if cash_after < 0:
            return apology('you have no enough money')
        db.execute("UPDATE users SET cash = :cash WHERE id = :user",
                          cash=cash_after, user = session["user_id"])

        check = db.execute("SELECT shares FROM purchase WHERE user_id = :user AND symbol = :symbol", user=session["user_id"], symbol=symbol)
        if not check:
            name = lookup(request.form.get('symbol'))['name']
            db.execute("INSERT INTO purchase(user_id, symbol, name, shares) VALUES (:user, :symbol, :name, :shares)",
                    user=session["user_id"], symbol=symbol, name=name, shares=shares)

        else:
            shares_updated = int(shares) + int(check[0]['shares'])
            db.execute("UPDATE purchase SET shares = :shares WHERE user_id = :user AND symbol = :symbol",
                    user=session["user_id"], symbol=symbol, shares= shares_updated)


        db.execute("INSERT INTO history(user_id, symbol, shares, price, date) VALUES (:user, :symbol, :shares, :price, :date)",
                user=session["user_id"], symbol=symbol, shares=shares, price=price_before, date=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

        flash('bought')
        return redirect('/')

    else:
        return render_template('buy.html')

@app.route("/history")
@login_required
def history():

    history = db.execute("SELECT symbol,shares,price,date FROM history WHERE user_id = :user", user=session["user_id"])
    for stock in history:
        symbol = history[0]['symbol']
        shares = history[0]['shares']
        price = history[0]['price']
        date = history[0]['date']

    return render_template('history.html', history = history)


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
    if request.method == 'POST':
        stock = lookup(request.form.get('symbol'))
        if stock == None:
            return apology('not exist', 403)

        return render_template('quoted.html', stock = stock)
    else:
        return render_template('quote.html')

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == 'POST':

        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation must be the same ", 403)
        elif db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username")):
            return apology('username is already taken', 403)
        db.execute('INSERT INTO users (username , hash) VALUES (:username , :hash)' ,
            username = request.form.get('username'), hash= generate_password_hash(request.form.get('password')))


        return redirect('/')
    else:
        return render_template('register.html')



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == 'POST':
        if not request.form.get('symbol'):
            return apology('you should precise valid stock', 403)

        if not request.form.get('shares') or int(request.form.get('shares')) <= 0 :
            return apology('you should precise a positive share number', 403)

        shares = request.form.get('shares')

        sym_available = db.execute("SELECT symbol FROM purchase WHERE user_id = :user AND symbol = :symbol",
                          user=session["user_id"], symbol=lookup(request.form.get('symbol'))['symbol'])

        symbol = lookup(request.form.get('symbol'))['symbol']


        if symbol == None:
            return apology('wrong stock', 403)

        cash = db.execute("SELECT cash FROM users WHERE id = :user",
                          user=session["user_id"])[0]['cash']

        price_before = lookup(request.form.get('symbol'))['price']

        cash_after = cash + float(price_before * float(shares))

        db.execute("UPDATE users SET cash = :cash WHERE id = :user",
                          cash=cash_after, user = session["user_id"])

        check = db.execute("SELECT shares FROM purchase WHERE user_id = :user AND symbol = :symbol", user=session["user_id"], symbol=symbol)


        if int(check[0]['shares']) - int(shares) < 0:
            return apology("you dont have enough stocks" , 403)

        shares_updated = int(check[0]['shares']) - int(shares)
        db.execute("UPDATE purchase SET shares = :shares WHERE user_id = :user AND symbol = :symbol",
                    user=session["user_id"], symbol=symbol, shares= shares_updated)

        db.execute("INSERT INTO history(user_id, symbol, shares, price, date) VALUES (:user, :symbol, :shares, :price, :date)",
                user=session["user_id"], symbol=symbol, shares= -int(shares), price=price_before, date=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))


        flash('sold')
        return redirect('/')

    else:
        return render_template('sell.html')

@app.route("/change", methods=["GET", "POST"])
@login_required
def change_pass():
    if request.method == 'POST':
        old = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        if not request.form.get("old_password"):
            return apology("must provide current password", 403)
        elif not request.form.get("password"):
            return apology("must provide new password", 403)
        elif not request.form.get("confirmation"):
            return apology("confirmation and new pass chould be the same", 403)
        elif not check_password_hash( old[0]["hash"] ,request.form.get("old_password")):
            return apology("old passowrd is wrong", 403)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("new password and confirmation must be the same ", 403)
        db.execute('UPDATE users SET hash = :hash WHERE id = :id' ,
                 id=session["user_id"], hash = generate_password_hash(request.form.get('password')))

        flash('password has been changed')
        return redirect('/')
    else:
        return render_template('change.html')

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
