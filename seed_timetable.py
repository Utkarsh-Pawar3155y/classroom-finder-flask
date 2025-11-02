# seed_timetable.py
# Run: python seed_timetable.py
# WARNING: This script will DROP existing tables and create a fresh database.

from app import app          # uses your existing Flask app & config
from models import db, Classroom, Booking
from datetime import time
import itertools
import random

def create_classrooms():
    """Create all Building-11 rooms (lectures + labs)."""
    rooms = []

    # Ground floor labs
    rooms += [("1016A", "Lab"), ("1016B", "Lab")]

    # Floors 1..4
    for floor_prefix in ("11", "12", "13", "14"):
        # lectures xx01 - xx20
        for i in range(1, 21):
            room_name = f"{floor_prefix}{i:02d}"
            rooms.append((room_name, "Lecture"))
        # labs xx21 - xx26
        for i in range(21, 27):
            room_name = f"{floor_prefix}{i}"
            rooms.append((room_name, "Lab"))
    return rooms

def time_str(t):
    """Return HH:MM string for datetime.time or (h,m)."""
    if isinstance(t, tuple):
        h, m = t
        return f"{h:02d}:{m:02d}"
    if isinstance(t, time):
        return t.strftime("%H:%M")
    return str(t)

def generate_slots():
    """
    Produce 1-hour lecture slots as (start_str, end_str) excluding 12:00-14:00 break.
    College hours 08:00-18:00, 1-hour slots.
    We'll create slots: 08-09,09-10,10-11,11-12, (break 12-14), 14-15,15-16,16-17,17-18
    """
    slots = [
        ("08:00","09:00"),
        ("09:00","10:00"),
        ("10:00","11:00"),
        ("11:00","12:00"),
        ("14:00","15:00"),
        ("15:00","16:00"),
        ("16:00","17:00"),
        ("17:00","18:00")
    ]
    return slots

def slots_to_lab_pairs(slots):
    """
    Create candidate 2-hour lab blocks from the slots list where consecutive slots exist:
    possible lab pairs: (14:00-16:00) i.e. slots[4] + slots[5], and (08:00-10:00) etc.
    We'll prefer afternoon lab pair (14-16), then morning (08-10), then (16-18).
    """
    # Map start->index
    idx = {s[0]: i for i, s in enumerate(slots)}
    pairs = []
    # common useful lab windows
    candidates = [("14:00","16:00"), ("08:00","10:00"), ("16:00","18:00"), ("10:00","12:00")]
    for start, end in candidates:
        # check start and end correspond to available slot boundaries
        # start slot should exist and next slot should align to end
        if start in idx:
            i = idx[start]
            # require that summing two consecutive slots produces end
            if i+1 < len(slots) and slots[i+1][1] == end:
                pairs.append((start, end))
    # if none found, fallback joining slots[0]+slots[1]
    if not pairs:
        pairs.append((slots[0][0], slots[1][1]))
    return pairs

def division_lists():
    it_divs = [f"IT-{chr(ord('A')+i)}" for i in range(6)]        # IT-A .. IT-F
    cs_divs = [f"CS-{chr(ord('A')+i)}" for i in range(12)]       # CS-A .. CS-L
    return it_divs, cs_divs

def faculty_pool():
    return [
        "Prof. Sharma", "Dr. Mehta", "Prof. Nair", "Dr. Kapoor", "Prof. Singh",
        "Dr. Verma", "Prof. Iyer", "Dr. Rao", "Prof. Kulkarni", "Dr. Gupta",
        "Prof. Patel", "Dr. Jain", "Prof. Bose", "Dr. Menon"
    ]

def subjects_pool():
    return [
        "Data Structures", "DBMS", "Operating Systems", "Computer Networks",
        "Mathematics", "Artificial Intelligence", "Machine Learning",
        "Web Technologies", "Cloud Computing", "Software Engineering",
        "Python Lab", "Java Lab", "Project Work"
    ]

def day_lists():
    it_days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    cs_days = ["Monday","Tuesday","Wednesday","Thursday"]
    return it_days, cs_days

def is_conflict(room_id, day, start, end):
    """Return True if room already booked for the day & time overlap."""
    # query bookings for this room and day and check overlap
    existing = Booking.query.filter_by(classroom_id=room_id, day=day).all()
    for b in existing:
        if not (end <= b.start_time or start >= b.end_time):
            return True
    return False

def seed_database():
    with app.app_context():
        # Reset DB (drop & recreate)
        db.drop_all()
        db.create_all()

        # Create classrooms
        rooms = create_classrooms()
        classroom_objs = []
        for rname, rtype in rooms:
            c = Classroom(room_name=rname, room_type=rtype)
            db.session.add(c)
            classroom_objs.append(c)
        db.session.commit()
        print(f"Created {len(classroom_objs)} classrooms.")

        # prepare pools and structures
        lecture_rooms = [c for c in Classroom.query.filter_by(room_type="Lecture").all()]
        lab_rooms = [c for c in Classroom.query.filter_by(room_type="Lab").all()]

        slots = generate_slots()
        lab_pairs = slots_to_lab_pairs(slots)
        it_divs, cs_divs = division_lists()
        it_days, cs_days = day_lists()
        faculties = faculty_pool()
        subjects = subjects_pool()

        # cycles for rooms and faculties to distribute evenly
        lecture_cycle = itertools.cycle(lecture_rooms)
        lab_cycle = itertools.cycle(lab_rooms)
        faculty_cycle = itertools.cycle(faculties)
        subject_cycle = itertools.cycle(subjects)

        # Helper: assign for department divisions
        def assign_for_division(div_name, days):
            """
            For each day assign:
              - 4 to 6 lecture 1-hour slots (mixed morning + afternoon)
              - 1 lab 2-hour block (prefers afternoon)
            """
            for day in days:
                # decide number of lecture hours for this division on this day (4..6)
                num_lectures = random.randint(4, 6)

                # prefer to allocate at least 2 in morning and at least 1 in afternoon if possible
                morning_indices = [i for i in range(0, 4) if i < len(slots)]
                afternoon_indices = [i for i in range(4, len(slots)) if i < len(slots)]

                chosen_indices = set()

                # ensure at least 2 morning (or as many as possible) if num_lectures >=2
                want_morning = min(2, num_lectures)
                morning_choices = random.sample(morning_indices, k=min(len(morning_indices), want_morning)) if morning_indices else []
                chosen_indices.update(morning_choices)

                # remaining to pick from both pools
                remaining = num_lectures - len(chosen_indices)
                combined_indices = [i for i in range(len(slots)) if i not in chosen_indices]
                if remaining > 0 and combined_indices:
                    # try to pick a balanced mix; sample without replacement
                    pick = min(remaining, len(combined_indices))
                    extra = random.sample(combined_indices, k=pick)
                    chosen_indices.update(extra)

                # Now assign lectures for chosen indices
                for idx in sorted(chosen_indices):
                    start, end = slots[idx]
                    # pick next lecture room without conflict
                    attempts = 0
                    room = None
                    while attempts <= len(lecture_rooms)*2:
                        candidate = next(lecture_cycle)
                        if not is_conflict(candidate.id, day, start, end):
                            room = candidate
                            break
                        attempts += 1
                    if room is None:
                        # couldn't find a room for this slot, skip it
                        continue
                    teacher = f"{div_name} - {next(faculty_cycle)}"
                    # subject is chosen but not stored in Booking model (kept for eventual extension)
                    subj = next(subject_cycle)
                    booking = Booking(
                        classroom_id=room.id,
                        teacher_name=teacher,
                        day=day,
                        start_time=start,
                        end_time=end
                    )
                    db.session.add(booking)

                # assign a lab (2-hour pair) - prefer first lab_pairs item
                assigned_lab = False
                for (lstart, lend) in lab_pairs:
                    attempts = 0
                    labroom = None
                    while attempts <= len(lab_rooms)*2:
                        candidate_lab = next(lab_cycle)
                        if not is_conflict(candidate_lab.id, day, lstart, lend):
                            labroom = candidate_lab
                            break
                        attempts += 1
                    if labroom:
                        teacher = f"{div_name} - {next(faculty_cycle)}"
                        booking = Booking(
                            classroom_id=labroom.id,
                            teacher_name=teacher,
                            day=day,
                            start_time=lstart,
                            end_time=lend
                        )
                        db.session.add(booking)
                        assigned_lab = True
                        break
                # if no lab assigned, we skip (rare)

        # Seed IT divisions (Mon-Fri)
        for div in it_divs:
            assign_for_division(div, it_days)

        # Seed CS divisions (Mon-Thu)
        for div in cs_divs:
            assign_for_division(div, cs_days)

        db.session.commit()
        print("Seeding complete. Bookings added.")

if __name__ == "__main__":
    seed_database()
    print("Database rebuilt and seeded successfully.")
