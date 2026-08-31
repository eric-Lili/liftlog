"""Convert a FitNotes .fitnotes backup (SQLite) into a LiftLog backup JSON.

    python3 tools/fitnotes-to-liftlog.py Backup.fitnotes liftlog-backup.json

Load the result in the app under Data -> Backup file -> Restore. Unlike the CSV
export this carries routines, categories and per-exercise weight increments.


FitNotes models a routine as a set of named sections (typically the days of a
split); LiftLog routines are flat, so each section becomes its own routine,
prefixed with the FitNotes routine name when there is more than one section.

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
routines = []
section_counts = {}
for r in db.execute("select routine_id, count(*) n from RoutineSection group by routine_id"):
    section_counts[r["routine_id"]] = r["n"]

sections = db.execute(
    """select rs._id sid, rs.name sname, rt._id rid, rt.name rname
       from RoutineSection rs join Routine rt on rt._id = rs.routine_id
       order by rt._id, rs.sort_order"""
).fetchall()

for s in sections:
    members = [
        ex_by_id[r["exercise_id"]]
        for r in db.execute(
            """select exercise_id from RoutineSectionExercise
               where routine_section_id = ? order by sort_order""",
            (s["sid"],),
        )
        if r["exercise_id"] in ex_by_id
    ]
    if not members:
        continue
    multi = section_counts.get(s["rid"], 0) > 1
    name = f"{s['rname']} · {s['sname']}" if multi else s["rname"]
    routines.append({"name": name, "exercises": members})

# --------------------------------------------------------------------- sets
# reps > 0 keeps bodyweight work (0 kg pull-ups) while dropping the
# duration/distance rows, which carry reps = 0.
sets = []
for r in db.execute(
    """select t.date, t.exercise_id, t.metric_weight w, t.reps
       from training_log t join exercise e on e._id = t.exercise_id
       where e.exercise_type_id = 0 and t.reps > 0
       order by t.date, t._id"""
):
    name = ex_by_id.get(r["exercise_id"])
    if not name:
        continue
    weight = round(float(r["w"]), 2)
    sets.append([r["date"], name, int(weight) if weight == int(weight) else weight, int(r["reps"])])

payload = {
    "format": "liftlog-backup",
    "version": 1,
    "exercises": exercises,
    "settings": settings,
    "routines": routines,
    "sets": sets,
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

print(f"exercises: {len(exercises)}")
print(f"  with explicit increment: {len(settings)}")
print(f"  duration/distance (kind=other): {sum(1 for e in exercises.values() if e['kind'] == 'other')}")
print(f"routines: {len(routines)}")
print(f"sets: {len(sets)}  ({sets[0][0]} .. {sets[-1][0]})")
