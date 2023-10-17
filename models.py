from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Venue(db.Model):
    __tablename__ = "venue"
    venue_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    name = db.Column(db.String, nullable=False)
    place = db.Column(db.String, nullable=False)
    location = db.Column(db.String, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)


class Show(db.Model):
    __tablename__ = "show"
    show_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    dateTime = db.Column(db.String, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.String, nullable=False)
    tags = db.Column(db.String, nullable=False)
    venue_id = db.Column(
        db.Integer, db.ForeignKey("venue.venue_id", ondelete="CASCADE"), nullable=False
    )


class User(db.Model):
    __tablename__ = "user"
    user_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    name = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False)


class user_show(db.Model):
    __tablename__ = "user_show"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False
    )
    show_id = db.Column(
        db.Integer, db.ForeignKey("show.show_id", ondelete="CASCADE"), nullable=False
    )
    seats = db.Column(db.Integer, nullable=False)
    booking_time = db.Column(db.String, nullable=False)
    rated = db.Column(db.String)
