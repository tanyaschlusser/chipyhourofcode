#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# chipyhourofcode.py
"""
The pages to make are:
    /about
    /location
    /register
    /confirmation/<id>
    /
"""
import os
import smtplib
import time
from email.mime.text import MIMEText

from sqlalchemy import create_engine  # MySQL 5.5.42

from flask import flash, Flask, g, jsonify
from flask import redirect, render_template, request, url_for
from flask.views import MethodView
from jinja2 import Environment, Template

with open(os.path.join(os.path.dirname(__file__), '.env')) as infile:
    for line in infile:
        if not line.startswith('#'):
            k, v = line.strip().split('=',1)
            os.environ[k] = v

## Setup
app = Flask(__name__)
app.config["STATIC_DIR"] = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'static')
app.config["SPEAKER_DIR"] = "img/speakers/"
app.config["SPONSOR_DIR"] = "img/sponsors/"

env = Environment()


## -------------------------------------------- Email parts ----- ##
def send_email(
        registration_details,
        msg,
        subject='Confirmation: ChiPy Hour of Code'):
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo()
    server.starttls()
    server.login(os.environ['GMAILU'], os.environ['GMAILP'])
    mailfrom = os.environ['GMAILU']
    mailto = registration_details['guardian_email']
    msg['Subject'] = subject
    msg['From'] = mailfrom
    msg['To'] = mailto
    server.sendmail(mailfrom, mailto, msg.as_string())
    server.close()


def send_confirmation(registration_details):
    send_email(
        registration_details,
        MIMEText("""
        You are confirmed to come to the Hour of Code
        hosted by ChiPy and Programming for Biologists at Northwestern:
        
        {attendee_name}
        and
        {guardian_name}
       
        If your plans change, please make room for others...
        Unregister at: http://chipyhourofcode.pythonanywhere.com/{conf_uri}

             Saturday 13 December 2015
                    9am - 11am
            Feinberg School of Medicine
              laptop|tablet|smartphone
             preferred but not required
        
        ❤
        ChiPy - the Chicago Python User Group
        and me, Tanya (organizing the event)
        """.format(conf_uri=url_for(
                'confirmation',
                uid=registration_details['unregister_uri']),
            **registration_details)
    ))


def send_unregister(registration_details):
    send_email(
        registration_details,
        MIMEText("""
        You have successfully unregistered for the Hour of Code
        hosted by ChiPy and Programming for Biologists at Northwestern:
        
        {attendee_name}
        and
        {guardian_name}

        We have deleted your information. Thank you!
        
        ❤
        ChiPy - the Chicago Python User Group
        and me, Tanya (organizing the event)
        """.format(**registration_details)
        ),
        subject='Unregistration Confirmed: ChiPy Hour of Code')


def send_waitlist(registration_details):
    send_email(
        registration_details,
        MIMEText("""
        You are on the waitlist for the Hour of Code
        hosted by ChiPy and Programming for Biologists at Northwestern:
        
        {attendee_name}
        and
        {guardian_name}

        We will send a confirmation email if you get off the wait list.
       
        If your plans change, please make room for others...
        Unregister at: http://chipyhourofcode.pythonanywhere.com/{conf_uri}
        
        ❤
        ChiPy - the Chicago Python User Group
        and me, Tanya (organizing the event)
        """.format(conf_uri=url_for(
                'confirmation',
                uid=registration_details['unregister_uri']),
            **registration_details)
        ),
        subject='Waitlist Confirmation: ChiPy Hour of Code')



## ----------------------------------------- Database parts ----- ##
def connect_db():
    engine = create_engine(os.environ['MYSQL_CONNECTION'])
    return engine
    

def get_db():
    """Set the flask 'g' value for _database, and return it."""
    db = getattr(g, "_database", None)
    if not db:
        db = g._database = connect_db()
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Set the flask 'g' value for _database, and return it."""
    db = getattr(g, '_database', None)
    if db:
        db.dispose()
    g._database = None


def db_query(query, args=[], commit=False):
    """Perform a query returning the database cursor if success else None.

    Use db_select for SELECT queries.
    Wrap the query with a try/except, catch the error, and return
    False if the query fails.
    """
    all_results = []
    db = get_db()
    con = db.connect()
    result = con.execute(query, args)
    if result and result.returns_rows:
        all_results = [r for r in result.fetchall()]
    con.close()
    return all_results
    

def db_select(query, args=[], columns=None):
    """Return the result of a select query as an array of dictionaries.

    Each dictionary has keys taken from the 'columns' argument, or else
    'col0' ... 'colN-1' for the N columns returned.

    If there is an error with the query, return None.

    Keyword arguments
    args -- passed to pg8000.cursor.execute() for a secure
            parameterized query.
            We use the default format: SELECT * FROM TABLE WHERE col1 = '%s'
    """
    results = db_query(query, args=args) 
    if results is None or len(results) == 0:
        return []
    elif len(results[0]) > len(columns):
        columns = list(columns) + ["col%d" % i for i in range(len(columns),len(results))]
    elif len(results[0]) < len(columns):
        columns = columns[0:len(results[0])]
    return [dict(zip(columns, result)) for result in results]


def db_select_one(query, args=[], columns=None):
    """Return the one-row result of a select query as a dictionary.

        If there are more than one rows, return only the contents of the first one.
        If there are no rows, return None.
    """
    rows = db_select(query, args=args, columns=columns)
    if rows is None or len(rows) == 0:
        return {}
    return rows[0]



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
    """Location just needs the google maps key."""
    return render_template('location.html',key=os.environ['GOOGLEMAPSKEY'])


@app.route("/register/", methods=['GET', 'POST'], strict_slashes=False)
def register():
    """Allow people to add/delete/change themselves.

    GET = form.
    POST = registration.
    """
    remaining = 19 - int(
        db_select_one(
            "SELECT sum(sent_confirmation) FROM attendee;"
        ).values().pop())
    if request.method == 'GET':
        return render_template('register.html', remaining=remaining)
    elif request.method == 'POST':
        # Check whether form is filled 
        attendee_data = dict(
            attendee_name=None,
            guardian_email=None,
            guardian_name=None
        )
        for k in attendee_data.keys():
            if k in request.form:
                attendee_data[k] = request.form[k]
        if None in attendee_data.values():
            flash('Missing data...we need everything, please.')
            return render_template(
                'register.html',
                attendee_data=attendee_data,
                error='Missing data...we need everything, please.'
            )
        # Check whether already registered.
        #  if so, flash 'already registered. tounregister go here: <>'
        #  else, check whether email exists for another registrant.
        result = db_select("""
                SELECT attendee_name,
                    guardian_email,
                    guardian_name,
                    unregister_uri,
                    registration_timestamp
                FROM attendee WHERE guardian_email = %s;
                """,
                args=[attendee_data['guardian_email']],
                columns=[
                    'attendee_name',
                    'guardian_email',
                    'guardian_name',
                    'unregister_uri',
                    'registration_timestamp'
                ])
        if len(result) > 0:
            for row in result:
                if row['attendee_name'] == attendee_data['attendee_name']:
                    flash("We think you have already registered...")
                    return render_template(
                        'register.html',
                        attendee_data=attendee_data,
                        remaining=remaining,
                        confirmation_link=url_for(
                            "confirmation",
                            uid=row['unregister_uri'])
                    )
        if len(result) > 0 and 'confirmed' not in request.form:
            # This adult is already bringing someone with a different name.
            #  Let them do it if they click again.
            flash("Click 'Register' again to confirm that this adult "
                  "is also bringing someone else..."
                  "(It's OK, we just want to make sure it's not a typo.)")
            return render_template(
                'register.html',
                attendee_data=attendee_data,
                get_confirmation=True,
                remaining=remaining
            )
        # Else add the person.
        parent = attendee_data['guardian_name'].strip()
        attendee_data['unregister_uri'] = uid = "{}{}{}".format(
                int(time.time()*100),
                parent[0],
                parent[-1])
        db_query("""
                INSERT INTO attendee
                (attendee_name, guardian_email, guardian_name, unregister_uri)
                VALUES (%s, %s, %s, %s)
                """,
                args=[attendee_data[k] for k in
                      ('attendee_name',
                       'guardian_email',
                       'guardian_name',
                       'unregister_uri')
                ],
                commit=True)
        return redirect(url_for('confirmation', uid=uid))


@app.route("/confirmation/<uid>", methods=['GET', 'POST'])
def confirmation(uid=None):
    if uid is None:
        flash("We could not find your registration..please register:")
        return redirect(url_for('register'))
    if request.method == 'GET':
        # If rank is less than 20, they're in.
        result = db_select_one("""
             SELECT   attendee_name,
                      guardian_email,
                      guardian_name,
                      unregister_uri,
                      sent_confirmation,
                      sent_waitlist,
                      rank
             FROM
            (SELECT   attendee_name,
                      guardian_email,
                      guardian_name,
                      unregister_uri,
                      sent_confirmation,
                      sent_waitlist,
                      @curRank := @curRank + 1 AS rank
             FROM     attendee, (SELECT @curRank := 0) r
             ORDER BY registration_timestamp
            ) AS a
            WHERE unregister_uri = %s
            """,
            args=[uid],
            columns=[
               "attendee_name",
               "guardian_email",
               "guardian_name",
               "unregister_uri",
               "sent_confirmation",
               "sent_waitlist",
               "rank"
        ])
        if result['rank'] < 20 and not result['sent_confirmation']:
            # Send confirmation email.
            send_confirmation(result)
            flash('Sent confirmation email')
            db_query("UPDATE attendee SET sent_confirmation = TRUE "
                     "WHERE unregister_uri = %s;",
                     args=[uid],
                     commit=True)
        elif result['rank'] >= 20 and not result['sent_waitlist']:
            # Else send waitlist email.
            send_waitlist(result)
            flash('Sent waitlist email')
            db_query("UPDATE attendee SET sent_waitlist = TRUE "
                     "WHERE unregister_uri = %s;",
                     args=[uid],
                     commit=True)
        # Display the result
        return render_template('confirmation.html', attendee_data=result)
    else:  # 'POST'
        if 'unregister' in request.form and request.form['unregister']:
            result = db_select_one("""
                 SELECT   attendee_name,
                          guardian_email,
                          guardian_name,
                          unregister_uri
                 FROM     attendee
                WHERE unregister_uri = %s
                """,
                args=[uid],
                columns=[
                 "attendee_name",
                 "guardian_email",
                 "guardian_name",
                 "unregister_uri"
            ])
            db_query(
                "DELETE FROM attendee WHERE unregister_uri = %s",
                args = [uid],
                commit=True)
            send_unregister(result)
            # Check for new rank < 20 and email them that they're in
            changes = db_select("""
                 SELECT   attendee_name,
                          guardian_email,
                          guardian_name,
                          unregister_uri
                 FROM
                (SELECT   attendee_name,
                          guardian_email,
                          guardian_name,
                          unregister_uri,
                          sent_confirmation,
                          sent_waitlist,
                          @curRank := @curRank + 1 AS rank
                 FROM     attendee, (SELECT @curRank := 0) r
                 ORDER BY registration_timestamp
                ) AS a
                WHERE rank < 20 AND sent_confirmation = FALSE
                """,
                columns=[
                 "attendee_name",
                 "guardian_email",
                 "guardian_name",
                 "unregister_uri"
            ])
            for change in changes:
                send_confirmation(change)
                db_query("UPDATE attendee SET sent_confirmation = TRUE "
                         "WHERE unregister_uri = %s;",
                         args=[change['unregister_uri']],
                         commit=True)
            result = None
        # Either confirm the registration or unregistration.
        return render_template('confirmation.html', attendee_data=result)


# app.secret_key is used by flask.session to encrypt the cookies
# (we need it for flash messages)
app.secret_key = os.urandom(24)


if __name__ == "__main__":
    app.run(debug=os.environ['DEBUG'])
