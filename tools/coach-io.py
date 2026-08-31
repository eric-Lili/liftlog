"""Read and write the LiftLog sync file from the coaching side.

    python3 tools/coach-io.py read  [--repo owner/name] [--out state.json]
    python3 tools/coach-io.py write --repo owner/name --coach coach.json

`read` fetches the shared state and prints a summary; with --out it also saves
the whole document for inspection.

`write` replaces ONLY the `coach` block. The app owns everything under `app`
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
    print(f"coach: {len(coach.get('suggestions') or {})} suggestions, "
          f"{len(coach.get('proposals') or [])} proposals, "
          f"brief {'yes' if coach.get('brief') else 'no'}")


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
    unknown = set(coach) - {"brief", "suggestions", "proposals"}
    if unknown:
        sys.exit(f"unexpected keys in the coach block: {sorted(unknown)}")

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
