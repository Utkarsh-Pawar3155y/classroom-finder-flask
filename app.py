from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Classroom, Booking
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'devkey'
SECRET_ACCESS_CODE = "ITDept@2025"

db.init_app(app)

# ---------------- Setup DB & sample data ----------------
with app.app_context():
    db.create_all()
    if not Classroom.query.first():
        sample_rooms = ["IT-201", "IT-202", "IT-Lab1", "IT-Lab2"]
        for room_name in sample_rooms:
            db.session.add(Classroom(room_name=room_name))
        db.session.commit()

# ---------------- Helper: Remove past bookings for today ----------------
def remove_past_bookings():
    now = datetime.now()
    today_str = now.strftime("%A")  # e.g., "Monday"
    bookings = Booking.query.filter_by(day=today_str).all()
    for b in bookings:
        booking_end_time = datetime.strptime(b.end_time, "%H:%M").time()
        if booking_end_time < now.time():
            db.session.delete(b)
    db.session.commit()

# ---------------- Helper: Check conflicts ----------------
def get_conflict_booking(room_name, day, start, end):
    classroom = Classroom.query.filter_by(room_name=room_name).first()
    if not classroom:
        return None
    bookings = Booking.query.filter_by(classroom_id=classroom.id, day=day).all()
    for b in bookings:
        if not (end <= b.start_time or start >= b.end_time):
            return b
    return None

# ---------------- Home: Timetable ----------------
@app.route('/', methods=['GET', 'POST'])
def home():
    remove_past_bookings()  # Clean up old bookings

    rooms = Classroom.query.all()
    selected_room_name = request.form.get('room_filter')  # dropdown POST value

    # Default: first classroom if none selected
    if not selected_room_name and rooms:
        selected_room_name = rooms[0].room_name

    # Filter rooms for display (only selected room)
    display_rooms = Classroom.query.filter_by(room_name=selected_room_name).all() if selected_room_name else []

    rooms_data = []
    for r in display_rooms:
        schedule = {}
        for b in r.bookings:
            if b.day.lower() == "sunday":
                continue
            schedule.setdefault(b.day, []).append((b.start_time, b.end_time, b.teacher_name))
        for day in schedule:
            schedule[day].sort(key=lambda x: x[0])
        rooms_data.append({
            "room_name": r.room_name,
            "room_type": r.room_type,
            "schedule": schedule
        })

    return render_template(
        'index.html',
        rooms_data=rooms_data,
        rooms=rooms,
        selected_room_name=selected_room_name
    )

# ---------------- Book Classroom ----------------
@app.route('/book', methods=['GET', 'POST'])
def book():
    rooms = Classroom.query.all()
    if request.method == 'POST':
        teacher = request.form['teacher']
        room = request.form['room']
        day = request.form['day']
        start = request.form['start']
        end = request.form['end']
        code = request.form['code']

        if code != SECRET_ACCESS_CODE:
            flash("Invalid access code. Booking denied.", "danger")
            return redirect(url_for('book'))

        conflict = get_conflict_booking(room, day, start, end)
        if conflict:
            flash(f"Room already booked by {conflict.teacher_name}", "warning")
            return redirect(url_for('book'))

        classroom = Classroom.query.filter_by(room_name=room).first()
        new_booking = Booking(
            classroom_id=classroom.id,
            teacher_name=teacher,
            day=day,
            start_time=start,
            end_time=end
        )
        db.session.add(new_booking)
        db.session.commit()
        flash("Booking successful!", "success")
        return redirect(url_for('home'))

    room_prefill = request.args.get('room', '')
    day_prefill = request.args.get('day', '')
    start_prefill = request.args.get('start', '')
    end_prefill = request.args.get('end', '')

    return render_template(
        'book.html',
        rooms=rooms,
        room_prefill=room_prefill,
        day_prefill=day_prefill,
        start_prefill=start_prefill,
        end_prefill=end_prefill
    )

# ---------------- Cancel Booking ----------------
@app.route('/cancel', methods=['GET', 'POST'])
def cancel():
    if request.method == 'POST':
        if 'fetch_bookings' in request.form:
            teacher = request.form['teacher']
            code = request.form['code']

            if code != SECRET_ACCESS_CODE:
                flash("Invalid access code.", "danger")
                return redirect(url_for('cancel'))

            bookings = Booking.query.filter_by(teacher_name=teacher).all()
            if not bookings:
                flash("No bookings found for this teacher.", "warning")
                return render_template('cancel.html', bookings=[], teacher=teacher, code=code)

            return render_template('cancel.html', bookings=bookings, teacher=teacher, code=code)

        elif 'cancel_selected' in request.form:
            teacher = request.form['teacher']
            code = request.form['code']

            if code != SECRET_ACCESS_CODE:
                flash("Invalid access code.", "danger")
                return redirect(url_for('cancel'))

            selected_ids = request.form.getlist('booking_ids')
            if not selected_ids:
                flash("No bookings selected for cancellation.", "warning")
                return redirect(url_for('cancel'))

            for bid in selected_ids:
                booking = Booking.query.get(int(bid))
                if booking and booking.teacher_name == teacher:
                    db.session.delete(booking)
            db.session.commit()
            flash("Selected bookings cancelled successfully!", "success")
            return redirect(url_for('home'))

    return render_template('cancel.html')

# ---------------- Check Availability ----------------
@app.route('/check_availability', methods=['GET', 'POST'])
def check_availability():
    remove_past_bookings()
    rooms = Classroom.query.all()
    available_rooms = []

    if request.method == 'POST':
        day = request.form['day']
        start = request.form['start']
        end = request.form['end']

        for room in rooms:
            bookings = Booking.query.filter_by(classroom_id=room.id, day=day).all()
            conflict = False
            for b in bookings:
                if not (end <= b.start_time or start >= b.end_time):
                    conflict = True
                    break
            if not conflict:
                available_rooms.append(room)

        return render_template(
            'check_availability.html',
            available_rooms=available_rooms,
            day=day,
            start=start,
            end=end
        )

    return render_template('check_availability.html', rooms=rooms)

# ---------------- Edit Booking ----------------
@app.route('/edit_booking', methods=['GET', 'POST'])
def edit_booking():
    rooms = Classroom.query.all()

    if request.method == 'POST':
        teacher = request.form['teacher']
        code = request.form['code']

        if code != SECRET_ACCESS_CODE:
            flash("Invalid access code. Cannot edit booking.", "danger")
            return redirect(url_for('edit_booking'))

        bookings = Booking.query.filter_by(teacher_name=teacher).all()
        if not bookings:
            flash("No bookings found for this teacher.", "warning")
            return redirect(url_for('edit_booking'))

        selected_id = request.form.get('booking_id')
        new_day = request.form.get('new_day')
        new_start = request.form.get('new_start')
        new_end = request.form.get('new_end')

        if selected_id and new_day and new_start and new_end:
            booking = Booking.query.get(int(selected_id))
            conflict = get_conflict_booking(booking.classroom.room_name, new_day, new_start, new_end)
            if conflict and conflict.id != booking.id:
                flash(f"Conflict! Room already booked by {conflict.teacher_name}", "warning")
                return redirect(url_for('edit_booking'))

            booking.day = new_day
            booking.start_time = new_start
            booking.end_time = new_end
            db.session.commit()
            flash("Booking updated successfully!", "success")
            return redirect(url_for('home'))

        return render_template('edit_booking.html', bookings=bookings)

    return render_template('edit_booking.html', bookings=None)

# ---------------- Run App ----------------
if __name__ == '__main__':
    app.run(debug=True)
