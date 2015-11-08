#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# chipyhourofcode.py
"""
The pages to make are:
    /about
    /location
    /register
    /register/<id>
    /
"""
import os
#from sqlalchemy import create_engine  # MySQL 5.5.42
import sqlite3

from flask import flash, Flask, g, jsonify
from flask import redirect, render_template, request, url_for
from flask.views import MethodView
from jinja2 import Environment, Template

## Local configuration settings -- database connection, passwords
def connect_db():
    #engine = create_engine(os.environ['MYSQL_CONNECTION'])
    #return engine.connect()
    conn = sqlite3.connect("reservations.db")
    

## Setup
app = Flask(__name__)
app.config["STATIC_DIR"] = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'static')
app.config["SPEAKER_DIR"] = "img/speakers/"
app.config["SPONSOR_DIR"] = "imag/sponsors/"

env = Environment()


## ----------------------------------------- Database parts ----- ##
def get_db():
    """Set the flask 'g' value for _database, and return it."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = connect_db()
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Set the flask 'g' value for _database, and return it."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
    g._database = None


def db_query(query, args=None, commit=False):
    """Perform a query returning the database cursor if success else None.

    Use db_select for SELECT queries.
    Wrap the query with a try/except, catch the error, and return
    False if the query fails.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    if commit:
        db.commit()
    return cur
    

def db_select(query, args=None, columns=None):
    """Return the result of a select query as an array of dictionaries.

    Each dictionary has keys taken from the 'columns' argument, or else
    'col0' ... 'colN-1' for the N columns returned.

    If there is an error with the query, return None.

    Keyword arguments
    args -- passed to pg8000.cursor.execute() for a secure
            parameterized query.
            We use the default format: SELECT * FROM TABLE WHERE col1 = '%s'
    """
    cur = db_query(query, args=args) 
    if cur is None:
        return None
    results = cur.fetchall()
    cur.close()
    if len(results) == 0:
        return None
    elif len(results[0]) > len(columns):
        columns = list(columns) + ["col%d" % i for i in range(len(columns),len(results))]
    elif len(results[0]) < len(columns):
        columns = columns[0:len(results[0])]

    return [dict(zip(columns, result)) for result in results]


def db_select_one(query, args=None, columns=None):
    """Return the one-row result of a select query as a dictionary.

        If there are more than one rows, return only the contents of the first one.
        If there are no rows, return None.
    """
    rows = db_select(query, args=args, columns=columns)
    if rows is None or len(rows) == 0:
        return {}
    return rows[0]


## ------------------------------------ False RESTful parts ----- ##
# This section will later be moved to a module devoted to serving
# a RESTful API. It will be replaced by modified versions of
# get_rest() and post_rest(), which will query the RESTful API
# rather than send off to different functions here.
#
# The functions all take key,value pairs (**kwargs)
# and return dictionaries that could be converted to valid JSON
def delete_nulls_arr(a):
    map(lambda row:[row.pop(k) for k in row.keys() if row[k] is None], a)

def delete_nulls_dict(d):
    [d.pop(k) for k in d.keys() if d[k] is None]


def get_profile(nickname="", **kwargs):
    update = {}
    result = dict(error = None,
        nickname=nickname,
        avatar="default.png" )

    if nickname != "" and nickname is not None:
        update = db_select_one("""
                SELECT nickname, avatar, first_name, last_name,
                       to_char(start_date, 'Month YYYY') AS start_date
                FROM user_details
                WHERE nickname = %s;""",
                args=[nickname],
                columns=["nickname", "avatar",
                    "first_name", "last_name", "start_date"])

        update['recommended_by_list'] = db_select(
                """SELECT
                    app_name, icon,
                    recipient_nickname AS name
                   FROM recommendation_view
                    WHERE recommender_nickname = %s;""",
                args=[nickname],
                columns=["app", "icon", "name"])    

        update['recommended_to_list'] = db_select(
                """SELECT
                    app_name, icon,
                    recommender_nickname AS name
                   FROM recommendation_view
                    WHERE recipient_nickname = %s;""",
                args=[nickname],
                columns=["app", "icon", "name"])

        update['review_list'] = db_select(
                """SELECT
                app_name, icon, review_date, review
                FROM user_details AS ud
                JOIN app_review AS ar
                    ON ar.user_id = ud.user_id
                JOIN app
                    ON ar.app_id = app.app_id
                WHERE ud.nickname = %s;""",
                args=[nickname],
                columns=["app", "icon", "review_date", "review"])

        delete_nulls_dict(update)
    result.update(update)
    return result


def get_rest(path, query={}):
    """To be replaced by a query to a RESTful API later."""
    apis = {
        "apps": get_apps,
        "login": get_login,
        "profile": get_profile}
    if path in apis:
        print "(Get) Query:", query
        result = apis[path](**query)
        if isinstance(result, dict):
            delete_nulls_dict(result)
        print "(Get) Result:", result
        import sys
        sys.stdout.flush()
        return result
    else:
        return None


def post_login(nickname=None, **kwargs):
    result = {}
    if nickname is None:
        result["error"]["nickname"] = "No user name given."
    else:
        db_query("INSERT INTO user_details (nickname) VALUES (%s)",
                 args=[nickname.lower()],
                 commit=True)
        result = db_select_one("""
                SELECT nickname, user_id, avatar
                FROM user_details WHERE nickname=%s;
                """,
                args=[nickname.lower()],
                columns=["nickname", "user_id", "avatar"])
        if len(result) == 0:
            result = {"error": "Odd, we just inserted the name."}
    return result


def post_profile(nickname=None, **kwargs):
    """Update the user's profile.

    kwargs should contain first_name, last_name, image.
    Image is right now (Dec 2014) a werkzeug.datastructures.FileStorage
    object but should be converted for send/receive via RESTful API
    """
    if nickname != None:
        result = db_select_one(
                "SELECT user_id FROM user_details WHERE nickname = %s;",
                args=[nickname],
                columns=["user_id"])
        if result is not None:
            user_id = result["user_id"]
            if "avatar" in kwargs:
                avatar = "avatar_%d.jpg" % user_id
                kwargs['avatar'].save(os.path.join(
                    app.config['STATIC_DIR'],
                    app.config['AVATAR_DIR'],
                    avatar))
                kwargs['avatar'] = avatar

            QUERY = "UPDATE user_details SET {QUERY_TEXT} WHERE user_id=%d;" % user_id
            query_keys = ('first_name', 'last_name', 'avatar')
            query_text = ", ".join(("{k}=%s".format(k=k) for k in query_keys
                                    if k in kwargs))
            query_data =  [kwargs[k] for k in query_keys if k in kwargs]
    
            cur = db_query(QUERY.format(QUERY_TEXT=query_text),
                     args=query_data,
                     commit=True)

            if cur is not None:
                result = {"success" : True}
        else:
            result = {"error": "Username not found."}
    else:      
        result = {"error": "Username not given."}
    return result
            


## ---------------------------------------------- Web parts ----- ##
@app.route("/")
def index():
    """The main page."""
    return render_template('index.html')


@app.route("/about")
def about():
    """About is a static page."""
    return render_template('about.html')


@app.route("/location")
def location():
    """Location is a static page."""
    return render_template('location.html')


@app.route("/register/", methods=['GET', 'POST'])
def register():
    """Allow people to add/delete/change themselves.

    GET = form.
    POST = registration.
    """
    if request.method == 'GET':
        return render_template('register.html')
    elif request.method == 'POST':
        print("Post to the DB here then render the confirmation")
        return redirect(url_for('confirmation', uid=uid))


@app.route("/confirmation/<uid>")
def confirmation():
    result = {}
    if request.method == 'POST':
        query = {}
        if 'nickname' in request.form:
            query['nickname'] = request.form['nickname']
            result = get_rest("login", query=query)
            if "create" in request.form:
                if "error" not in result:
                    # The nickname is in use already
                    result = {
                        "error":
                        "Sorry, cannot create username -- already in use."}
                else:
                    # Then the nickname is available for use. Create it.
                    result = post_rest("login", query=query)
                    result["created"] = "true"
            else:  # login
                # is there  an error?
                print "Result for 'login':", result
        else:
           result["error"] = "No user id entered."

        print "RESULT:", result
        if "user_id" in result:
            flash('Login successful')
            
        return jsonify(**result)

    elif request.method == 'GET':
        return render_template('login.html')


@app.route("/modify/<uid>", methods=['GET', 'POST'])
def modify(uid=None):
    # Fetch the uid and render
    if uid is None:
        flash('No registration ID given -- try signing up')
        redirect(url_for('register'))
    if request.method == 'GET':
        print("Get the data and render the form filled with"
                "flash message that they're already registered")
        return("Placeholder -- get {}".format(uid))
    else:
        print("Modify the db. If unregistering flash the message"
                "that they've successfully unregistered")
        flash('Successfully modified. Thank you!')
        return("Placeholder -- post {}".format(uid))


if __name__ == "__main__":
    app.run(debug=os.environ['DEBUG'])
