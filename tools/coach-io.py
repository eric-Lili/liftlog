"""Read and write the LiftLog sync file from the coaching side.

    python3 tools/coach-io.py read  [--repo owner/name] [--out state.json]
    python3 tools/coach-io.py write --repo owner/name --coach coach.json

`read` fetches the shared state and prints a summary; with --out it also saves
the whole document for inspection.

`write` replaces ONLY the `coach` block (brief, suggestions, proposals,
questions, checkins,
shortSessions). The app owns everything under `app`
and this script will not touch it — that separation is what stops the phone and
the coach clobbering each other, so it is enforced here rather than trusted.

Authentication uses the `gh` CLI, so whatever `gh auth` is logged in as applies.
"""
import argparse
import base64
import datetime
import json
import subprocess
import sys


def gh(args, **kw):
    return subprocess.run(["gh", *args], capture_output=True, text=True, **kw)


def fetch(repo, path="state.json"):
    r = gh(["api", f"repos/{repo}/contents/{path}"])
    if r.returncode != 0:
        if "Not Found" in r.stderr:
            return None, None
        sys.exit(f"could not read {repo}/{path}:\n{r.stderr.strip()}")
    meta = json.loads(r.stdout)
    raw = base64.b64decode(meta["content"]).decode("utf-8")
    return json.loads(raw), meta["sha"]


def summarise(doc):
    app = doc.get("app", {})
    sets = app.get("sets", [])
    by_ex = {}
    for s in sets:
        by_ex.setdefault(s["exercise"], []).append(s)
    dates = sorted({s["date"] for s in sets})
    print(f"updated {doc.get('updatedAt', '?')} by {doc.get('updatedBy', '?')[:8]}  epoch {app.get('epoch')}")
    print(f"{len(sets)} sets across {len(by_ex)} exercises, {len(dates)} training days"
          f"{f' ({dates[0]} .. {dates[-1]})' if dates else ''}")
    print(f"{len(app.get('routines', []))} routines, {len(app.get('sessions', []))} sessions")
    prof = app.get("profile") or {}
    if any(prof.values()):
        print("profile: " + "; ".join(f"{k}={v}" for k, v in prof.items() if v))
    coach = doc.get("coach") or {}
    questions = coach.get("questions") or []
    bank = coach.get("checkins") or []
    shorts = coach.get("shortSessions") or []
    print(f"coach: {len(coach.get('suggestions') or {})} suggestions, "
          f"{len(coach.get('proposals') or [])} proposals, "
          f"{len(questions)} questions, {len(bank)} staged check-ins, "
          f"{len(shorts)} short sessions, "
          f"brief {'yes' if coach.get('brief') else 'no'}")

    # The check-ins are the half of the picture the sets cannot carry, so they
    # go in the summary rather than being left for whoever thinks to open the
    # file. An unanswered question is one you already asked — asking it again
    # is how a coach stops being listened to.
    checkins = app.get("checkins") or []
    answered = {c.get("questionId") for c in checkins if c.get("questionId")}
    unanswered = [q for q in questions if q.get("id") not in answered]
    if unanswered:
        print(f"\nstill unanswered ({len(unanswered)}):")
        for q in unanswered:
            print(f"  [{q.get('id')}] {q.get('text', '')}")
    used = {c.get("bankId") for c in checkins if c.get("bankId")}
    unused = [c for c in bank if c.get("id") not in used]
    if bank:
        print(f"\nstaged bank: {len(unused)} of {len(bank)} still unused")
        for c in bank:
            when = c.get("when") or {}
            rule = (f"after {when['exercise']}" if when.get("exercise")
                    else f"if {when['idleDays']}+ days idle" if when.get("idleDays")
                    else "any session")
            mark = " " if c.get("id") in used else "*"
            print(f"  {mark} [{c.get('id')}] ({c.get('scope', 'session')}, {rule}) {c.get('text', '')}")

    if shorts:
        print("\nshort sessions on offer:")
        for x in shorts:
            mins = f"{x['minutes']} min" if x.get("minutes") else "?"
            print(f"  [{x.get('id')}] {x.get('name')} ({mins}) — {', '.join(x.get('exercises') or [])}")

    # How long you have been away, which is what decides whether the app is
    # currently showing that offer at all.
    days = sorted({s["date"] for s in sets})
    if days:
        last = datetime.date.fromisoformat(days[-1])
        idle = (datetime.date.today() - last).days
        print(f"\nlast trained {days[-1]} — {idle} day{'' if idle == 1 else 's'} ago")

    recent = sorted(checkins, key=lambda c: str(c.get("at", "")), reverse=True)[:12]
    if recent:
        print(f"\n{len(checkins)} check-ins, most recent first:")
        for c in recent:
            when = str(c.get("at", ""))[:10]
            if c.get("kind") == "question":
                print(f"  {when}  Q: {c.get('question', '')}")
                print(f"              A: {c.get('text', '')}")
            elif c.get("kind") == "lapse":
                print(f"  {when}  away {c.get('days', '?')} days — said: {c.get('text', '')}")
                continue
            else:
                where = c.get("exercise") or c.get("sessionName")
                bits = [b for b in (where, c.get("choice") or c.get("feel")) if b]
                print(f"  {when}  " + " — ".join(bits))
                if c.get("bankId"):
                    print(f"              asked: {c.get('question', '')}")
                if c.get("text"):
                    print(f"              said:  {c['text']}")


def fail(msg):
    raise ValueError(msg)


def validate_coach(coach):
    """Reject anything the app could not draw. Raises ValueError."""
    if not isinstance(coach, dict):
        fail("the coach block must be a JSON object")
    unknown = set(coach) - {"brief", "suggestions", "proposals", "questions",
                            "checkins", "shortSessions"}
    if unknown:
        fail(f"unexpected keys in the coach block: {sorted(unknown)}")

    # A question the app cannot draw or cannot file an answer against is worse
    # than no question, so it is rejected here rather than silently dropped on
    # the phone.
    for q in coach.get("questions") or []:
        if not isinstance(q, dict) or not q.get("id") or not q.get("text"):
            fail(f"every question needs an id and text: {q!r}")
    ids = [q["id"] for q in coach.get("questions") or []]
    if len(ids) != len(set(ids)):
        fail("question ids must be unique")

    # The staged bank. The phone reads these with no way to ask about anything
    # it does not understand, so a malformed entry is rejected here rather than
    # silently dropped at the gym.
    seen = set()
    for c in coach.get("checkins") or []:
        if not isinstance(c, dict) or not c.get("id") or not c.get("text"):
            fail(f"every staged check-in needs an id and text: {c!r}")
        if c["id"] in seen:
            fail(f"duplicate staged check-in id: {c['id']}")
        seen.add(c["id"])
        if c["id"] == "built-in":
            fail("'built-in' is the app's own check-in id — pick another")
        if c.get("scope", "session") not in ("session", "exercise"):
            fail(f"scope must be 'session' or 'exercise': {c['id']}")
        opts = c.get("options")
        if opts is not None and (not isinstance(opts, list) or not all(isinstance(o, str) for o in opts)):
            fail(f"options must be a list of strings: {c['id']}")
        when = c.get("when") or {}
        if not isinstance(when, dict) or set(when) - {"exercise", "idleDays"}:
            fail(f"when may only hold 'exercise' and/or 'idleDays': {c['id']}")
        if "idleDays" in when and not isinstance(when["idleDays"], int):
            fail(f"when.idleDays must be a whole number of days: {c['id']}")
        if c.get("scope") == "exercise" and not when.get("exercise"):
            fail(f"an exercise-scope check-in needs when.exercise: {c['id']}")

    # Short sessions are offered when a lapse is detected, and are started with
    # one tap — so an entry with no exercises would hand over an empty workout.
    seen = set()
    for x in coach.get("shortSessions") or []:
        if not isinstance(x, dict) or not x.get("id") or not x.get("name"):
            fail(f"every short session needs an id and a name: {x!r}")
        if x["id"] in seen:
            fail(f"duplicate short session id: {x['id']}")
        seen.add(x["id"])
        ex = x.get("exercises")
        if not isinstance(ex, list) or not ex or not all(isinstance(n, str) and n for n in ex):
            fail(f"a short session needs a non-empty list of exercise names: {x['id']}")
        if len(ex) > 5:
            fail(f"{x['id']}: {len(ex)} exercises is not a short session")
        if "minutes" in x and not isinstance(x["minutes"], int):
            fail(f"minutes must be a whole number: {x['id']}")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["read", "write"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--path", default="state.json")
    ap.add_argument("--out")
    ap.add_argument("--coach", help="JSON file holding the new coach block")
    a = ap.parse_args()

    doc, sha = fetch(a.repo, a.path)
    if doc is None:
        sys.exit(f"{a.repo}/{a.path} does not exist yet — sync from the app first.")

    if a.action == "read":
        summarise(doc)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=1)
            print(f"\nwrote {a.out}")
        return

    if not a.coach:
        sys.exit("write needs --coach pointing at a JSON file")
    with open(a.coach, encoding="utf-8") as fh:
        coach = json.load(fh)
    try:
        validate_coach(coach)
    except ValueError as err:
        sys.exit(str(err))

    # Re-read immediately before writing to narrow the race, and only ever
    # replace `coach`.
    doc, sha = fetch(a.repo, a.path)
    doc["coach"] = coach
    body = json.dumps({
        "message": "coach: update assessment",
        "content": base64.b64encode(json.dumps(doc, indent=1).encode("utf-8")).decode("ascii"),
        "sha": sha,
    })
    r = gh(["api", "-X", "PUT", f"repos/{a.repo}/contents/{a.path}", "--input", "-"], input=body)
    if r.returncode != 0:
        sys.exit(f"write failed:\n{r.stderr.strip()}")
    print("coach block updated.")


if __name__ == "__main__":
    main()
