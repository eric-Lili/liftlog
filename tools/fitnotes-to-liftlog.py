"""Convert a FitNotes .fitnotes backup (SQLite) into a LiftLog backup JSON.

    python3 tools/fitnotes-to-liftlog.py Backup.fitnotes liftlog-backup.json

Load the result in the app under Data -> Backup file -> Restore. Unlike the CSV
export this carries routines, categories and per-exercise weight increments.


FitNotes models a routine as a set of named sections (typically the days of a
split), which maps directly onto LiftLog: a Routine is the programme, and each
section becomes a Workout inside it.

Every kind of set is carried over: weight x reps, weight x time (planks),
weight x distance (farmers walks) and distance x time (cardio). LiftLog stores
a duration in seconds and a distance in metres, whichever unit FitNotes used.

An exercise whose FitNotes type is not one of the four is imported as
kind="other", which the app reads as "not classified" and resolves from the
name — set it by hand on the exercise's own screen if the guess is wrong.
"""
import json
import sqlite3
import sys

SRC, OUT = sys.argv[1], sys.argv[2]

db = sqlite3.connect(SRC)
db.row_factory = sqlite3.Row

# ---------------------------------------------------------------- exercises
categories = {r["_id"]: r["name"] for r in db.execute("select _id, name from Category")}

# FitNotes' exercise_type_id, as seen in real backups. Anything else is left
# unclassified rather than guessed at: a wrong kind means a log screen asking
# for the wrong numbers.
KINDS = {
    0: "weight",           # weight x reps
    1: "distance-time",    # cardio
    2: "weight-distance",  # loaded carries
    3: "weight-time",      # loaded holds
}

exercises = {}
settings = {}
ex_by_id = {}
kind_by_id = {}
unknown_types = {}
for r in db.execute("select _id, name, category_id, exercise_type_id, weight_increment from exercise"):
    name = r["name"].strip()
    if not name:
        continue
    kind = KINDS.get(r["exercise_type_id"], "other")
    if kind == "other":
        unknown_types.setdefault(r["exercise_type_id"], []).append(name)
    ex_by_id[r["_id"]] = name
    kind_by_id[r["_id"]] = kind
    exercises[name] = {
        "category": categories.get(r["category_id"], "Uncategorized"),
        "kind": kind,
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
# `unit` doubles as the weight unit on weight rows and the distance unit on
# distance rows. Only 2 = metres is confirmed against a real backup; the rest
# are inferred, so any row using one is reported below for a sanity check.
DISTANCE_TO_M = {0: 1000.0, 1: 1609.344, 2: 1.0, 3: 0.9144}
DISTANCE_UNIT_NAME = {0: "km", 1: "miles", 2: "metres", 3: "yards"}


def tidy(v):
    v = round(float(v), 2)
    return int(v) if v == int(v) else v


sets = []
distance_units = {}
for r in db.execute(
    """select t._id, t.date, t.exercise_id, t.metric_weight w, t.reps, t.unit,
              t.distance, t.duration_seconds
       from training_log t order by t.date, t._id"""
):
    name = ex_by_id.get(r["exercise_id"])
    kind = kind_by_id.get(r["exercise_id"])
    if not name or kind == "other":
        continue

    # Ids are derived from FitNotes' own row ids so re-running the converter
    # produces the same identities rather than fresh random ones.
    s = {"id": f"fn{r['_id']}", "date": r["date"], "exercise": name, "notes": "", "src": "fitnotes"}
    # Weight is optional everywhere except weight x reps — a bodyweight plank
    # is a plank — but zero is a real answer there, so it is always written.
    if kind == "weight":
        # reps > 0 keeps bodyweight work (0 kg pull-ups) and drops the empty
        # rows FitNotes leaves behind.
        if not r["reps"]:
            continue
        s["weight"] = tidy(r["w"])
        s["reps"] = int(r["reps"])
    else:
        if "weight" in kind and r["w"]:
            s["weight"] = tidy(r["w"])
        if "distance" in kind and r["distance"]:
            distance_units[r["unit"]] = distance_units.get(r["unit"], 0) + 1
            s["distance"] = tidy(float(r["distance"]) * DISTANCE_TO_M.get(r["unit"], 1.0))
        if "time" in kind and r["duration_seconds"]:
            s["duration"] = int(r["duration_seconds"])
        # A carry with no distance and a hold with no time record nothing.
        if not any(k in s for k in ("distance", "duration")):
            continue
    sets.append(s)

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

by_kind = {}
for ex in exercises.values():
    by_kind[ex["kind"]] = by_kind.get(ex["kind"], 0) + 1

print(f"exercises: {len(exercises)}")
print(f"  with explicit increment: {len(settings)}")
for k in sorted(by_kind):
    print(f"  {k}: {by_kind[k]}")
for type_id, names in sorted(unknown_types.items()):
    print(f"  ! exercise type {type_id} is not one LiftLog knows — left unclassified: {', '.join(names)}")
print(f"routines: {len(routines)}  ({sum(len(r['workouts']) for r in routines)} workouts)")
print(f"sets: {len(sets)}  ({sets[0]['date']} .. {sets[-1]['date']})")
for unit, n in sorted(distance_units.items()):
    note = "" if unit == 2 else "  (unit id inferred — check the numbers)"
    print(f"  {n} distance rows read as {DISTANCE_UNIT_NAME.get(unit, unit)}{note}")
