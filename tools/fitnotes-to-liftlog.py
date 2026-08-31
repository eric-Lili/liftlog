"""Convert a FitNotes .fitnotes backup (SQLite) into a LiftLog backup JSON.

    python3 tools/fitnotes-to-liftlog.py Backup.fitnotes liftlog-backup.json

Load the result in the app under Data -> Backup file -> Restore. Unlike the CSV
export this carries routines, categories and per-exercise weight increments.


FitNotes models a routine as a set of named sections (typically the days of a
split), which maps directly onto LiftLog: a Routine is the programme, and each
section becomes a Workout inside it.

Only weight x reps sets are carried over — FitNotes' duration and distance
entries (planks, farmers walks, cardio) have no equivalent in LiftLog. The
exercises themselves are still imported so routines referencing them stay
intact; they are tagged kind="other".
"""
import json
import sqlite3
import sys

SRC, OUT = sys.argv[1], sys.argv[2]

db = sqlite3.connect(SRC)
db.row_factory = sqlite3.Row

# ---------------------------------------------------------------- exercises
categories = {r["_id"]: r["name"] for r in db.execute("select _id, name from Category")}

exercises = {}
settings = {}
ex_by_id = {}
for r in db.execute("select _id, name, category_id, exercise_type_id, weight_increment from exercise"):
    name = r["name"].strip()
    if not name:
        continue
    ex_by_id[r["_id"]] = name
    exercises[name] = {
        "category": categories.get(r["category_id"], "Uncategorized"),
        "kind": "weight" if r["exercise_type_id"] == 0 else "other",
    }
    # FitNotes' per-exercise increment reflects the actual equipment (a machine
    # with 2.5 kg steps, dumbbells in 2 kg jumps), so it beats a global default.
    if r["weight_increment"]:
        settings[name] = {"increment": float(r["weight_increment"])}

# ----------------------------------------------------------------- routines
# FitNotes nests days inside a routine as "sections", which is the same shape
# LiftLog uses: a Routine is the programme, and each Workout inside it is one
# session's work.
routines = []
for rt in db.execute("select _id, name, notes from Routine order by _id"):
    workouts = []
    for s in db.execute(
        "select _id, name from RoutineSection where routine_id = ? order by sort_order",
        (rt["_id"],),
    ):
        members = [
            ex_by_id[r["exercise_id"]]
            for r in db.execute(
                """select exercise_id from RoutineSectionExercise
                   where routine_section_id = ? order by sort_order""",
                (s["_id"],),
            )
            if r["exercise_id"] in ex_by_id
        ]
        if members:
            workouts.append({"id": f"w{s['_id']}", "name": s["name"], "exercises": members})
    if workouts:
        routines.append({"id": f"r{rt['_id']}", "name": rt["name"], "weeks": None, "workouts": workouts})

# --------------------------------------------------------------------- sets
# reps > 0 keeps bodyweight work (0 kg pull-ups) while dropping the
# duration/distance rows, which carry reps = 0.
sets = []
for r in db.execute(
    """select t._id, t.date, t.exercise_id, t.metric_weight w, t.reps
       from training_log t join exercise e on e._id = t.exercise_id
       where e.exercise_type_id = 0 and t.reps > 0
       order by t.date, t._id"""
):
    name = ex_by_id.get(r["exercise_id"])
    if not name:
        continue
    weight = round(float(r["w"]), 2)
    sets.append({
        # Ids are derived from FitNotes' own row ids so re-running the converter
        # produces the same identities rather than fresh random ones.
        "id": f"fn{r['_id']}",
        "date": r["date"],
        "exercise": name,
        "weight": int(weight) if weight == int(weight) else weight,
        "reps": int(r["reps"]),
        "notes": "",
        "src": "fitnotes",
    })

payload = {
    "format": "liftlog-backup",
    "version": 2,
    "exercises": exercises,
    "settings": settings,
    "routines": routines,
    "sessions": [],
    "goals": [],
    "coachSuggestions": {},
    "sets": sets,
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

print(f"exercises: {len(exercises)}")
print(f"  with explicit increment: {len(settings)}")
print(f"  duration/distance (kind=other): {sum(1 for e in exercises.values() if e['kind'] == 'other')}")
print(f"routines: {len(routines)}  ({sum(len(r['workouts']) for r in routines)} workouts)")
print(f"sets: {len(sets)}  ({sets[0]['date']} .. {sets[-1]['date']})")
