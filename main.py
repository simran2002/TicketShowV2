from datetime import time
from typing import ByteString
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, User, user_show, Show, Venue
from flask_cors import CORS
from views import initialize_views
from celery import Celery, Task
# from models import db, User
from send_mail import send_email
from jinja2 import Template
from celery.schedules import crontab
from dateutil import parser
from datetime import date, datetime
import requests
import json
import calendar

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///TicketShow_database.sqlite3"
app.config["DEBUG"] = False
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
app.secret_key = "shushhh"
celery = Celery(broker_url="redis://127.0.0.1:6379/1",
    result_backend="redis://127.0.0.1:6379/2",
    timezone="Asia/Kolkata")

@app.route("/get/users", methods=['GET'])
def getAllUsers():
    users = User.query.filter(User.role == 'user').all()
    filtered = []
    for user in users:
        filtered.append(
            {
                'user_id' : user.user_id,
                'name' : user.name,
                'email' : user.email
            }
        )
    # print(filtered)
    return jsonify({'data' : filtered})

@app.route("/get/user_show/<int:userId>", methods=['GET'])
def getUserShow(userId):
    user_shows = user_show.query.filter(user_show.user_id == userId).all()
    users = User.query.filter(User.role == 'user').all()
    for bookings in user_shows:
        if parser.parse(bookings.booking_time).date() == datetime.now().date():
            return jsonify({'send' : 'false'})
    return jsonify({'send' : 'true'})

@app.route("/get/user_monthly/<int:userId>", methods = ['GET'])
def monthlyUsers(userId):
    filtered = []
    d = {}
    month_temp = (datetime.now().month)-1
    user_shows = user_show.query.filter(user_show.user_id == userId).all()
    for bookings in user_shows:
        booking = datetime.strptime(bookings.booking_time, '%Y-%m-%d %H:%M:%S.%f')
        
        month = calendar.month_name[booking.month]
        year = booking.strftime('%Y')
        date_in_words = f"{month} {booking.day}, {year}"

        if booking.month == month_temp:
            show = Show.query.filter(Show.show_id == bookings.show_id).first()
            venue = Venue.query.filter(Venue.venue_id == show.venue_id).first()
            
            if (show.name in d.keys()) and (d[show.name]['Booking Date'] == booking.date()):
                d[show.name]["Tickets Booked"] += 1
                
                continue
            d[show.name] = {'Tickets Booked' : 1, 'Booking Date' : date_in_words, 'Venue' : venue.name}
            filtered.append(d)
    return jsonify({'data' : filtered})

db.init_app(app)
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(role = "admin").first()
    if not admin:
        admin = User(name="SIMRAN", username="simran", email="simran@gmail.com", password="2345", role="admin")
        db.session.add(admin)
        db.session.commit()
    initialize_views(app)
    
    @celery.on_after_finalize.connect
    def setup_periodic_tasks(sender, **kwargs):
        print("in celery")
        sender.add_periodic_task(5.0, test_func.s())
        sender.add_periodic_task(crontab(hour=18, minute=0), daily_task.s(), name='daily')
        sender.add_periodic_task(crontab(0, 10, day_of_month='1'), monthly_task.s(), name='monthly')

    @celery.task()
    def test_func():
        print("yaha aa gya")

    @celery.task()
    def daily_task():
        all_users = requests.get("http://localhost:8081/get/users").json()['data']

        for user in all_users:
            id = user['user_id']
            try:
                send = requests.get(f"http://localhost:8081/get/user_show/{id}").json()
                if send['send'] == 'true':
                    with open("public/send_mail.html","r") as b:
                        print("yahya hu")
                        html=Template(b.read())
                        print("sent yayayayaya")
                        send_email(user['email'], subject="Daily Reminder", message=html.render(user = user))
            except:
                pass
    
    @celery.task()
    def monthly_task():
        all_users = requests.get("http://localhost:8081/get/users").json()['data']
        for user in all_users:
            print(user)
            id = user['user_id']
            dict = requests.get(f"http://localhost:8081/get/user_monthly/{id}")
            d = []
            if dict.json()['data'] != []:
                d = dict.json()['data'][0]
            with open("public/send_monthly.html","r") as b:
                html=Template(b.read())
                send_email(user['email'], subject="Monthly Progress Report", message=html.render(d=d,user=user))



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
