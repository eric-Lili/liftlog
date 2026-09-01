#!/usr/bin/env bash
#
# The weekly coach run. A scheduled Claude Code session, with the workout-coach
# agent driving it, that reads the synced training log and writes an assessment
# and any questions back — then puts a desktop notification up so the review is
# something you are told about rather than something you have to remember to go
# and look for.
#
# Installed as a systemd user timer; see `tools/liftlog-review.timer`.
#
#   LIFTLOG_REPO   the private data repo (default eric-Lili/liftlog-data)
#
set -uo pipefail

REPO="${LIFTLOG_REPO:-eric-Lili/liftlog-data}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

read -r -d '' PROMPT <<EOF
This is the scheduled weekly review — nobody is watching, so do the whole job
and leave the result where it will be found.

Work against the repo ${REPO}, using ${HERE}/coach-io.py as always.

1. Read the current state. Pay particular attention to the check-ins and to any
   questions of yours that have since been answered.
2. Decide whether there is anything to say. Nothing logged AND nothing answered
   since your last brief means write no new brief at all.
3. Otherwise write the coach block: the brief, any per-exercise calls, any
   proposals, and at most two or three questions — carrying forward the ones
   still unanswered and dropping the ones now answered.
4. Refill the staged bank either way — this part is not optional and happens
   even on a silent week. Answered entries are spent, and an empty bank leaves
   the app with only its own generic card until you next run. Keep three to six
   staged, most of them carrying a `when` rule.

Write the coach JSON with python3 (a heredoc is not available to you here):
python3 -c "import json,pathlib; pathlib.Path('/tmp/coach.json').write_text(json.dumps({...}))"

Then end your reply with a single line, on its own, of at most 110 characters:

NOTIFY: <the one thing worth knowing, or the word 'skip' if you wrote no brief>

Make that line specific — "bench has stalled 6 weeks, 2 questions for you"
tells me whether to open the app; "review complete" does not.
EOF

# The prompt goes in on stdin, not as an argument: --allowedTools is variadic,
# so a trailing positional gets eaten as one more tool name and Claude exits
# complaining it was given no prompt at all.
out="$(printf '%s' "$PROMPT" | claude -p --agent workout-coach \
  --allowedTools "Bash(python3:*),Read" 2>&1)"
status=$?

echo "$out"

line="$(printf '%s\n' "$out" | grep -m1 '^NOTIFY:' | sed 's/^NOTIFY:[[:space:]]*//')"

if [ $status -ne 0 ]; then
  notify-send -a LiftLog -u low "LiftLog review failed" "${line:-see journalctl --user -u liftlog-review}"
  # Fail loudly: a silent success in the journal is how a broken weekly job
  # goes unnoticed for a month.
  exit 1
elif [ -z "$line" ] || [ "$line" = "skip" ]; then
  # Nothing was written, so there is nothing to interrupt for. A notification
  # that says "no news" every Sunday is how notifications get turned off.
  :
else
  notify-send -a LiftLog "Your coach has looked at your training" "$line"
fi
