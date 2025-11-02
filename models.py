# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(50), unique=True, nullable=False)
    room_type = db.Column(db.String(50), default="Lecture")
    capacity = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Classroom {self.room_name}>"

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    teacher_name = db.Column(db.String(100), nullable=False)
    day = db.Column(db.String(20), nullable=False)         # e.g., "Monday"
    start_time = db.Column(db.String(10), nullable=False)  # "09:00"
    end_time = db.Column(db.String(10), nullable=False)    # "10:00"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classroom = db.relationship('Classroom', backref='bookings')

    def __repr__(self):
        return f"<Booking {self.classroom_id} {self.day} {self.start_time}-{self.end_time}>"
