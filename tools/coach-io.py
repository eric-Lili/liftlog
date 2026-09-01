"""Read and write the LiftLog sync file from the coaching side.

    python3 tools/coach-io.py read  [--repo owner/name] [--out state.json]
    python3 tools/coach-io.py write --repo owner/name --coach coach.json

`read` fetches the shared state and prints a summary; with --out it also saves
the whole document for inspection.

`write` replaces ONLY the `coach` block (brief, suggestions, proposals, questions). The app owns everything under `app`
and this script will not touch it — that separation is what stops the phone and
the coach clobbering each other, so it is enforced here rather than trusted.

Authentication uses the `gh` CLI, so whatever `gh auth` is logged in as applies.
"""
import argparse
import base64
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
    print(f"coach: {len(coach.get('suggestions') or {})} suggestions, "
          f"{len(coach.get('proposals') or [])} proposals, "
          f"{len(questions)} questions, "
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
    recent = sorted(checkins, key=lambda c: str(c.get("at", "")), reverse=True)[:12]
    if recent:
        print(f"\n{len(checkins)} check-ins, most recent first:")
        for c in recent:
            when = str(c.get("at", ""))[:10]
            if c.get("kind") == "question":
                print(f"  {when}  Q: {c.get('question', '')}")
                print(f"              A: {c.get('text', '')}")
            else:
                bits = [b for b in (c.get("sessionName"), c.get("feel"), c.get("text")) if b]
                print(f"  {when}  " + " — ".join(bits))


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
    if not isinstance(coach, dict):
        sys.exit("the coach block must be a JSON object")
    unknown = set(coach) - {"brief", "suggestions", "proposals", "questions"}
    if unknown:
        sys.exit(f"unexpected keys in the coach block: {sorted(unknown)}")

    # A question the app cannot draw or cannot file an answer against is worse
    # than no question, so it is rejected here rather than silently dropped on
    # the phone.
    for q in coach.get("questions") or []:
        if not isinstance(q, dict) or not q.get("id") or not q.get("text"):
            sys.exit(f"every question needs an id and text: {q!r}")
    ids = [q["id"] for q in coach.get("questions") or []]
    if len(ids) != len(set(ids)):
        sys.exit("question ids must be unique")

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
