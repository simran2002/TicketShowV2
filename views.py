from ast import arg
from email import message
from re import A
from flask_restful import Resource, reqparse, marshal, Api, fields, marshal_with, abort
from flask import current_app, jsonify, send_from_directory, session
from datetime import datetime, time, timedelta
from models import User, Venue, Show, user_show, db
import os
import json
from datetime import datetime
from jwt_auth import auth_required
import jwt
import pandas as pd
from flask_caching import Cache
import matplotlib
from send_mail import send_email
from jinja2 import Template
from celery.schedules import crontab
from dateutil import parser
from datetime import date, datetime
from celery import Celery, Task

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

api = Api()
cache = Cache()
# celery_app = Celery("Application Jobs")

create_user_parser = reqparse.RequestParser()
create_user_parser.add_argument("firstname")
create_user_parser.add_argument("lastname")
create_user_parser.add_argument("username")
create_user_parser.add_argument("email")
create_user_parser.add_argument("password")

login_user_parser = reqparse.RequestParser()
login_user_parser.add_argument("email")
login_user_parser.add_argument("password")

create_show_parser = reqparse.RequestParser()
create_show_parser.add_argument("showName")
create_show_parser.add_argument("price")
create_show_parser.add_argument("dateTime")
create_show_parser.add_argument("available_seats")
create_show_parser.add_argument("rating")
create_show_parser.add_argument("tags")
create_show_parser.add_argument("venue")

create_venue_parser = reqparse.RequestParser()
create_venue_parser.add_argument("venueName")
create_venue_parser.add_argument("place")
create_venue_parser.add_argument("location")
create_venue_parser.add_argument("capacity")

create_booking_parser = reqparse.RequestParser()
create_booking_parser.add_argument("userId")
create_booking_parser.add_argument("showId")
create_booking_parser.add_argument("rating")
create_booking_parser.add_argument("seats")


def initialize_views(app):
    app = app
    api.init_app(app)
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config['CACHE_REDIS_HOST'] = "localhost"
    app.config['CACHE_REDIS_PORT'] = 6379
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379"
    app.config['CACHE_DEFAULT_TIMEOUT'] = 200
    cache.init_app(app)
    # celery_app = celery_task.initialize_celery(app)

class Signup(Resource):
    def post(self):
        args = create_user_parser.parse_args()
        firstname = args.get("firstname", None)
        lastname = args.get("lastname", None)
        email = args.get("email", None)
        password = args.get("password", None)
        username = args.get("username", None)

        if firstname is None:
            abort(404, message="Firstname not provided")

        if lastname is None:
            abort(404, message="Lastname not provided")

        if email is None:
            abort(404, message="Please provide a valid email id")

        if username is None:
            abort(404, message="Please provide a valid email id")

        if password is None:
            abort(404, message="Password not provided")

        user = User.query.filter(User.email == email).first()
        if user:
            abort(404, message="User with this email already exists...")

        name = firstname + " " + lastname
        newuser = User(
            name=name, username=username, email=email, password=password, role="user"
        )

        db.session.add(newuser)
        db.session.commit()

        uid = newuser.user_id
        app = current_app._get_current_object()
        jt = jwt.encode(
            {"uid": uid, "exp": datetime.utcnow() + timedelta(minutes=30)},
            app.config["SECRET_KEY"],
        )
        # return valid_user
        return jsonify(
            {
                "userId": uid,
                "name": newuser.name,
                "username": newuser.username,
                "userRole": newuser.role,
                "token": jt,
            }
        )


class Login(Resource):
    def post(self):
        args = login_user_parser.parse_args()
        print(args)
        email = args.get("email", None)
        password = args.get("password", None)

        if email is None:
            return {"message": "Please provide a valid email"}, 404

        if password is None:
            return {"message": "Password can not be empty"}, 404

        user = User.query.filter(User.email == email).first()
        app = current_app._get_current_object()
        if user:
            if user.password == password:
                uid = user.user_id
                jt = jwt.encode(
                    {"uid": uid, "exp": datetime.utcnow() + timedelta(minutes=30)},
                    app.config["SECRET_KEY"],
                )
                # return valid_user
                return jsonify(
                    {
                        "userId": uid,
                        "name": user.name,
                        "username": user.username,
                        "userRole": user.role,
                        "token": jt,
                    }
                )
            else:
                abort(404, message="Invalid Password")

        else:
            abort(404, message="User with this email does not exist")


class Logout(Resource):
    @auth_required
    def get(self, userId=None):
        if userId:
            user = User.query.filter(User.user_id == userId).first()
            if user:
                return user
            else:
                abort(404, message="Invalid user id")
        else:
            abort(404, message="Enter user id")


class Profile(Resource):
    @auth_required
    @cache.cached(timeout=2)
    def get(self, userId=None):
        results = []
        if userId:
            user = User.query.filter(User.user_id == userId).first()
            if user:
                user_shows = user_show.query.filter(user_show.user_id == userId).all()
                if user_shows:
                    for shows in user_shows:
                        temp_show = Show.query.filter(
                            Show.show_id == shows.show_id
                        ).first()
                        venue = Venue.query.filter(
                            Venue.venue_id == temp_show.venue_id
                        ).first()
                        d = {
                            "bookingId": shows.id,
                            "Show": temp_show.name,
                            "Venue": venue.name,
                            "ShowDateTime": temp_show.dateTime,
                            "Rate": shows.rated,
                            "SeatsBooked": shows.seats,
                        }
                        results.append(d)
                    return results
                else:
                    return {"msg": "No booking history. Book a show now"}, 404
            else:
                abort(404, message="User with this id does not exist")

        else:
            abort(404, message="Provide user id")


class Booking(Resource):
    @auth_required
    @cache.cached(timeout=10)
    def post(self):
        args = create_booking_parser.parse_args()
        print(type(args))
        user_id = args.get("userId", None)
        show_id = args.get("showId", None)
        rating = args.get("rating", None)
        seats = args.get("seats", None)
        if user_id is None:
            abort(404, message="User id not provided")
        if show_id is None:
            abort(404, message="Show id not provided")

        user = user_show.query.filter(
            user_show.user_id == user_id, user_show.show_id == show_id
        ).first()
        if user:
            abort(404, message="This show is already booked by you")
        new_booking = user_show(
            user_id=user_id,
            show_id=show_id,
            seats=seats,
            booking_time=datetime.now(),
            rated=rating,
        )
        db.session.add(new_booking)
        db.session.commit()

        return jsonify(
            {"bookingId": new_booking.id, "bookingTime": new_booking.booking_time}
        )

    def get(self, showId=None):
        if showId is None:
            abort(404, message="Show id not provided")

        bookings = user_show.query.filter(user_show.show_id == showId).all()
        show = Show.query.filter(Show.show_id == showId).first()

        total_seats = 0
        for booking in bookings:
            total_seats += booking.seats

        return jsonify({"data": total_seats})


class VenueApi(Resource):
    @auth_required
    @cache.cached(timeout=10)
    def get(self, venueId=None):
        if venueId:
            ven = Venue.query.filter(Venue.venue_id == venueId).first()
            if ven:
                return jsonify(
                    {
                        "venue_id": ven.venue_id,
                        "name": ven.name,
                        "place": ven.place,
                        "location": ven.location,
                        "capacity": ven.capacity,
                    }
                )
            else:
                return "Venue does not exist", 200

        else:
            abort(404, message="Enter venue id")

    def post(self):
        args = create_venue_parser.parse_args()
        print(args)
        venue_name = args.get("venueName", None)
        place = args.get("place", None)
        location = args.get("location", None)
        if venue_name is None:
            abort(404, message="Venue name not provided")

        if place is None:
            abort(404, message="Provide a valid Place")

        if location is None:
            abort(404, message="Provide a valid Location")

        ven = Venue.query.filter(Venue.name == venue_name).first()
        if ven:
            abort(404, message="Venue with this Name already exists...")

        new_venue = Venue(
            name=venue_name,
            place=place,
            location=location,
            capacity=args.get("capacity", "undefined"),
        )
        db.session.add(new_venue)
        db.session.commit()

        return jsonify(
            {
                "id": new_venue.venue_id,
                "name": new_venue.name,
                "place": new_venue.place,
                "location": new_venue.location,
                "capacity": new_venue.capacity,
            }
        )

    def put(self, venueId=None):
        args = create_venue_parser.parse_args()

        venue_name = args.get("venueName", None)
        place = args.get("place", None)
        location = args.get("location", None)
        capacity = args.get("capacity", None)

        ven = Venue.query.filter(Venue.venue_id == venueId).first()
        if ven:
            if venue_name:
                ven.name = venue_name
            if place:
                ven.place = place
            if location:
                ven.location = location
            if capacity:
                ven.capacity = capacity
            db.session.commit()

            return jsonify(
                {
                    "id": ven.venue_id,
                    "name": ven.name,
                    "place": ven.place,
                    "location": ven.location,
                    "capacity": ven.capacity,
                }
            )
        else:
            abort(404, "invalid card")

    def delete(self, venueId=None):
        if venueId:
            ven = Venue.query.filter(Venue.venue_id == venueId).first()
            if ven:
                db.session.delete(ven)
                db.session.commit()
                return "Venue deleted successfully", 200
            else:
                abort(404, message="Venue does not exists")
        else:
            abort(404, message="Enter venue id")


class ShowApi(Resource):
    @auth_required
    @cache.cached(timeout=10)
    def get(self, showId=None, venueId=None):
        if showId:
            show = Show.query.filter(Show.show_id == showId).first()
            if show:
                return jsonify(
                    {
                        "id": show.show_id,
                        "name": show.name,
                        "dateTime": show.dateTime,
                        "price": show.price,
                        "rating": show.rating,
                        "available_seats": show.available_seats,
                        "tags": show.tags,
                    }
                )
            else:
                return "Show does not exist with this id", 200
        elif venueId:
            show = Show.query.filter(Show.venue_id == venueId).first()
            if show:
                return jsonify(
                    {
                        "id": show.showId,
                        "name": show.name,
                        "dateTime": show.dateTime,
                        "price": show.price,
                        "available_seats": show.available_seats,
                        "tags": show.tags,
                    }
                )
            else:
                return "Show does not exist with this venue id", 200
        else:
            abort(404, message="Enter show id or venue id")

    def post(self):
        args = create_show_parser.parse_args()
        print(args)
        show_name = args.get("showName", None)
        price = args.get("price", None)
        dateTime = args.get("dateTime", None)
        seats = args.get("available_seats", None)
        venue = args.get("venue", None)
        if show_name is None:
            abort(404, message="Show name not provided")

        if price is None:
            abort(404, message="Show price not provided")

        if seats is None:
            abort(404, message="Available seats for the show not provided")

        if venue is None:
            abort(404, message="Provide a venue for the show")
        if dateTime is None:
            abort(404, message="Provide a time for the show")

        ven = Venue.query.filter(Venue.name == venue).first()
        if ven:
            new_show = Show(
                name=show_name,
                price=price,
                dateTime=dateTime,
                available_seats=seats,
                rating=args.get("rating", None),
                tags=args.get("tags", None),
                venue_id=int(ven.venue_id),
            )
            db.session.add(new_show)
            db.session.commit()
        else:
            abort(404, message="Venue with this Name does not exists...")

        return jsonify(
            {
                "id": new_show.show_id,
                "name": new_show.name,
                "dateTime": new_show.dateTime,
                "price": new_show.price,
                "available_seats": new_show.available_seats,
                "tags": new_show.tags,
            }
        )

    @auth_required
    def put(self, showId=None):
        args = create_show_parser.parse_args()
        print(args)
        show_name = args.get("showName", None)
        price = args.get("price", None)
        timings = args.get("timings", None)
        seats = args.get("available_seats", None)

        show = Show.query.filter(Show.show_id == showId).first()
        if show:
            if show_name:
                show.name = show_name
            if price:
                show.price = price
            if timings:
                show.timings = timings
            if seats:
                show.available_seats = seats

            db.session.commit()
            return jsonify(
                {
                    "id": show.show_id,
                    "name": show.name,
                    "price": show.price,
                    "dateTime": show.dateTime,
                    "available_seats": show.available_seats,
                    "tags": show.tags,
                }
            )
        else:
            abort(404, message="invalid card")

    @auth_required
    def delete(self, showId=None):
        if showId:
            show = Show.query.filter(Show.show_id == showId).first()
            if show:
                db.session.delete(show)
                db.session.commit()
                return "Show deleted successfully", 200
            else:
                abort(404, message="Show does not exists")
        else:
            abort(404, message="Show venue id")


class GetVenueList(Resource):
    @auth_required
    @cache.cached(timeout=10)
    def get(self):
        venue = Venue.query.all()
        filtered_json = []
        for ven in venue:
            shows = Show.query.filter(Show.venue_id == ven.venue_id)
            venueShows = []
            for show in shows:
                venueShows.append(
                    {
                        "id": show.show_id,
                        "name": show.name,
                        "price": show.price,
                        "dateTime": show.dateTime,
                        "available_seats": show.available_seats,
                        "tags": show.tags,
                        "ratings": show.rating,
                    }
                )
            filtered_json.append(
                {
                    "venue_id": ven.venue_id,
                    "name": ven.name,
                    "place": ven.place,
                    "location": ven.location,
                    "capacity": ven.capacity,
                    "shows": venueShows,
                }
            )
        return {"data": filtered_json}


class GetShowList(Resource):
    @auth_required
    def get(self, venueId=None):
        if venueId:
            filtered_json = []
            shows = Show.query.filter(Show.venue_id == venueId)
            for show in shows:
                filtered_json.append(
                    {
                        "id": show.show_id,
                        "name": show.name,
                        "price": show.price,
                        "dateTime": show.dateTime,
                        "available_seats": show.available_seats,
                        "tags": show.tags,
                        "ratings": show.rating,
                    }
                )
            return {"data": filtered_json}
        else:
            abort(404, message="Venue Id not provided")


class GetUserRole(Resource):
    @auth_required
    def get(self, userId=None):
        if userId:
            user = User.query.filter(User.user_id == userId).first()
            return user.role, 200
        else:
            abort(404, message="User Id not provided")


class ExportVenue(Resource):
    @auth_required
    def get(self, venueId=None):
        username = []
        shows = []
        bookings = []
        ratings = []

        if venueId:
            showsList = Show.query.filter(Show.venue_id == venueId).all()
            print(showsList)
            venue_name = Venue.query.filter(Venue.venue_id == venueId).first().name
            if showsList:
                i = 0
                for show in showsList:
                    # i += 1
                    # print(i)
                    # print(type(show))
                    show_bookings = user_show.query.filter(
                        user_show.show_id == show.show_id
                    ).all()
                    for record in show_bookings:
                        if record.rated != "":
                            ratings.append(record.rated)
                        else:
                            ratings.append("Not rated")

                        username.append(
                            (
                                User.query.filter(
                                    User.user_id == record.user_id
                                ).first()
                            ).name
                        )
                        shows.append(
                            (
                                Show.query.filter(
                                    Show.show_id == record.show_id
                                ).first()
                            ).name
                        )
                        bookings.append(record.booking_time)

                Username = pd.Series(username)
                Shows = pd.Series(shows)
                Bookings = pd.Series(bookings)
                Ratings = pd.Series(ratings)

                df = pd.DataFrame(
                    {
                        "User": Username,
                        "Shows": Shows,
                        "Booked On": Bookings,
                        "Ratings": Ratings,
                    }
                )
                df.to_csv(f"{venue_name}.csv", index=False)
            else:
                abort(404,message= "no bookings for this venue")

        else:
            abort(404, message="Venue id not provided")


class ShowSummary(Resource):
    @auth_required
    @cache.cached(timeout=10)
    def get(self, venueId=None):
        if venueId:
            venue_shows = Show.query.filter(Show.venue_id == venueId).all()
            if venue_shows:
                booking_records = {}
                rating_records = {}
                for show in venue_shows:
                    booked = user_show.query.filter(
                        user_show.show_id == show.show_id
                    ).all()

                    if booked:
                        booking_records[show.name] = len(booked)

                        ratings = 0
                        total_rating = 0
                        for records in booked:
                            if records.rated != None:
                                if records.rated != "":
                                    total_rating += 1
                                    ratings += int(records.rated)
                        if total_rating != 0:
                            rating_records[show.name] = np.round(
                                (ratings / total_rating), 2
                            )
                        else:
                            rating_records[show.name] = 0
                    else:
                        continue

                if booking_records == {}:
                    abort(404, "No bookings exists for the shows")
                x_axis_1 = booking_records.keys()
                y_axis_1 = booking_records.values()

                bar = plt.figure()
                plt.bar(x_axis_1, y_axis_1)
                plt.title("Show Bookings")
                plt.xlabel("Shows")
                plt.ylabel("Bookings Done")
                bar.savefig("./src/assets/booking" + str(venueId) + ".png")

                x_axis_2 = rating_records.keys()
                y_axis_2 = rating_records.values()

                bar = plt.figure()
                plt.bar(x_axis_2, y_axis_2)
                plt.title("Show Ratings")
                plt.xlabel("Shows")
                plt.ylabel("Average Ratings")
                bar.savefig("./src/assets/rating" + str(venueId) + ".png")
            else:
                abort(404, message="No show exists in this venue")
        else:
            abort(404, message="Venue Id not provided")


class UserRating(Resource):
    def put(self, bookingId=None, rating=None):
        if bookingId:
            if rating:
                booking = user_show.query.filter(user_show.id == bookingId).first()

                booking.rated = rating
                db.session.commit()
                return "Show rated successfully", 200
            else:
                abort(404, message="Rating for the show not provided")
        else:
            abort(404, message="Booking Id not provided")


api.add_resource(GetShowList, "/api/getVenueShow/<int:venueId>")
api.add_resource(Booking, "/api/booking/<int:showId>", "/api/booking")
api.add_resource(Signup, "/api/signup")
api.add_resource(Login, "/api/login")
api.add_resource(Logout, "/api/logout/<int:uid>")
api.add_resource(VenueApi, "/api/venue/<int:venueId>", "/api/venue")
api.add_resource(ShowApi, "/api/show/<int:showId>", "/api/show")
api.add_resource(GetVenueList, "/api/getVenue")
api.add_resource(Profile, "/api/userProfile/<int:userId>")
api.add_resource(GetUserRole, "/api/getUserRole/<int:userId>")
api.add_resource(ExportVenue, "/api/exportVenue/<int:venueId>")
api.add_resource(ShowSummary, "/api/summary/<int:venueId>")
api.add_resource(UserRating, "/api/rating/<int:bookingId>/<string:rating>")

