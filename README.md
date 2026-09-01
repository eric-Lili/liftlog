# LiftLog

An offline-first workout logger with automatic weight and rep progression
suggestions. Built as a companion to FitNotes — it imports your FitNotes
export and carries on from there, adding the one thing FitNotes doesn't do:
telling you what to load next.

## How the pieces are named

```
Routine      a complete programme, run for a block of weeks
  Workout      one session's worth of work, exercises in a fixed order
    Exercise     position within the workout matters
      Set          the measures its exercise records (see below)

Session      one performance of a Workout. Starts when you log the first
             set, ends when you tap Complete, and owns the sets between.
```

Reordering exercises during a session is saved back to the **workout**, so the
order sticks next time. Skipping one — a broken machine, a day you don't feel
like it — applies to **that session only** and leaves the workout alone.

A session can be **completed**, **switched** to a different workout (the clock
and anything logged carry over — for when you started the wrong one), or
**discarded**. Discarding removes the workout record but keeps the sets: you
did lift them. Completing a workout with nothing logged discards it rather than
recording an empty one.

## On the phone

Every screen is a history entry, so the back and forward gestures walk them the
way they do in any other app. The one exception is the post-session debrief:
once answered it is replaced rather than pushed, so swiping back cannot file the
same check-in twice.

**Pull down to sync.** The browser's own pull-to-refresh reloaded the whole app
and dropped you back on Today, which is never what the gesture meant here — so
it is suppressed (on `html`, which is the scrolling element; setting it on
`body` alone does nothing) and wired to a sync instead. Pull past the halfway
mark and release. A reorder drag can only start on a grip handle, so the two
gestures never collide.

## What a set is

Not everything is weight × reps, so an exercise declares which measures its sets
carry — its **kind**:

| Kind | Records | Typically |
|------|---------|-----------|
| Weight × reps | weight, reps | the lifts |
| Weight × time | weight, duration | planks and other holds |
| Weight × distance | weight, distance | farmers walks, sled work |
| Distance & time | distance, duration | cardio |

Weight is optional on everything but the first — a bodyweight plank is a plank —
and may be negative on assisted machines. Durations are stored in seconds and
distances in metres however they were typed, so two sets are always comparable.

The kind decides what the log screen asks for and how the set reads back
("80 kg × 5", "12kg 1:00", "25kg 20m", "5.2km 28:00"). It is taken from the
FitNotes import, then from a set you log, then from the exercise's name — and
you can set it by hand under **Exercise settings**. Changing it never rewrites
sets already logged.

## Why

FitNotes is a good logger but has no progression logic — you decide the
weight every session yourself. LiftLog keeps FitNotes' fast, offline,
no-account approach and puts a suggested next weight × reps at the top of
every exercise screen.

## How progression works

Progression is about load, so it applies to weight × reps work. Two rules,
picked per exercise:

- **Heavy** — for compounds you don't take to failure. The weight goes up on
  a clock: a small increment (default 1.25 kg) every N weeks, regardless of
  whether you hit a rep target. Reps stay where they are.
- **Accessory** — double progression. Add one rep per session until you reach
  the top of the rep range, then add weight and drop back to the bottom.

Compound lifts are classified as heavy automatically by name; everything else
defaults to accessory. Either can be overridden per exercise, along with the
equipment, increment, cadence and rep range, under **Progression settings**.

**Equipment decides what is loadable.** A barbell takes plates on both ends, so
with 1.25 kg plates its smallest real jump is 2.5 kg — suggesting 96.25 kg for a
squat is useless because it cannot be built. Barbell lifts therefore progress in
twice-the-smallest-plate steps and show the per-side breakdown. Because a name
alone cannot tell a back squat from an EZ-bar curl, the bar assumption is
checked against your own history: if what you have logged for a lift can't be
built from the configured bar and plates, LiftLog stops making plate claims
about it and falls back to the generic increment.

On an **assisted** machine the number is help rather than load, so log it
negative; progress there runs toward zero and the app words it as "less
assistance" rather than "+2.5 kg".

Suggestions read the top weight of your last session. Heavy lifts keep the rep
count you actually work at (the most common across those sets), so one short
set doesn't drag the target down; accessories use the limiting set, because
double progression should only advance when every set clears the range.

After **more than three weeks** without a given lift, the suggestion switches
to repeating your last session rather than adding load — coming back from a
layoff you've detrained, and progressing from where you left off is how people
get hurt.

**Time and distance work is logged, not programmed.** Adding five seconds to a
plank on a clock would be arithmetic dressed up as coaching, so for those kinds
the app shows your best set from last time and asks you to match or beat it —
with the same layoff warning when you've been away.

## Setup

1. Open the site and add it to your home screen (Chrome: ⋮ → *Add to home
   screen*). It then runs standalone and works with no connection at all.
2. Load your data — either route works:
   - **From a `.fitnotes` backup** (best): the repo's `tools/fitnotes-to-liftlog.py`
     converts one into a LiftLog backup file, which carries your exercises,
     categories, routines, per-exercise increments and full history. Load it
     under **Data → Backup file → Restore**.
   - **From a CSV export**: FitNotes → Settings → Backup → Export, then
     **Data → Import CSV**. Simpler to get hold of, but carries sets only —
     no routines and no per-exercise increments.

FitNotes routines are a set of named sections, usually the days of a split;
LiftLog routines are flat, so the converter turns each section into its own
routine (`Moose · Day 1 - Squat Lower Body`).

FitNotes' duration and distance work — planks, farmers walks, cardio — comes
across with everything else: the converter reads each exercise's FitNotes type
and carries the times and distances the sets were logged with. An exercise whose
type LiftLog doesn't recognise is imported unclassified and settled from its
name, which you can correct on its own screen.

## Data

Everything lives in this browser on this device — there is no account, no
server, and nothing is transmitted. That also means clearing site data wipes
it, so export now and then:

- **Data → Backup file → Download** — the complete picture, including routines,
  progression settings and your profile. This is the one to keep.
- **Data → Download CSV** — sets only, in FitNotes' own columns (including
  `Distance`, `Distance Unit` and `Time`), for feeding the Ledger coaching app
  or moving back to FitNotes.

## Sync and the coach

LiftLog keeps a copy of your training as `state.json` in a **private** GitHub
repo. That file is the shared surface: the app writes your training to it, and
the coaching agent reads it and writes an assessment back.

Ownership is structural rather than by agreement:

```
state.json
  app     sets, exercises, routines, sessions, settings, goals, profile,
          prefs, checkins, proposalsDone
          — written only by LiftLog
  coach   brief, suggestions, proposals, questions, checkins
          — written only by the coach
```

Note which side owns the check-ins: the coach *asks* (`coach.questions`) but
the app *records* (`app.checkins`). An answer is something you said, so it sits
with the rest of your data and survives the coach rewriting its block.

A push carries the remote's own `coach` block back untouched, so neither side
can clobber the other. An `epoch` counter settles the rest: it increments on any
wholesale replace (CSV import, restore, erase), and the higher epoch wins. An
empty client never overwrites a non-empty server — browsers evict storage, and a
returning-empty app must not destroy your history.

**Setup:** create a private repo, then create a fine-grained token scoped to
**that repo only**, Contents: read & write. Enter both under **Data → Sync**.

Do **not** give the token access to the `liftlog` repo. Every GitHub Pages site
on an account shares one origin, and `localStorage` is keyed by origin — a token
that could rewrite the app itself would be a real problem. Scoped correctly the
worst case is that someone reads your training.

The token is stored under its own key, so it never appears in a backup file or
in the synced data.

### What the coach can do

Accepting or dismissing a proposal is remembered in `app.checkins`' neighbour,
`app.proposalsDone` — app-owned, because a sync replaces the whole `coach` block
with the server's copy and a card you had already dealt with would otherwise come
straight back. The list is pruned as the coach stops offering those proposals.

The **Coach** tab shows its written assessment, any per-exercise calls (which
replace the app's own suggestion for that lift), and **proposals** — structural
changes like adding an exercise, changing a progression rule, or reworking a
workout. Proposals are applied by the app from a fixed vocabulary only when you
accept them; an unrecognised one is inert. Nothing the agent writes changes your
programme on its own.

### Check-ins

The log knows what you lifted. It cannot know that the last set moved badly, or
that the shoulder complained, or that you slept four hours — and that is
precisely the context a coach reasons from. So the conversation runs both ways.

**After you tap Complete**, the app asks one question. Sometimes it is its own —
easy, about right, or hard, plus a note — and sometimes it is one the coach
staged for you. It takes a couple of seconds and skipping is a real option: a
prompt you cannot dismiss is a prompt you learn to lie to.

### The staged bank

The coach runs from a timer on a desktop, so it cannot be asked anything while
you are at the gym. Instead it writes a bank of check-ins ahead of time, each
with a rule saying when it applies, and the app picks one offline:

```
coach.checkins
  { id, text, options?, note?, scope?, when? }

  when: { exercise: "Deadlift" }   a session that included that lift
        { idleDays: 8 }            the first session back after 8 days off
        omitted                    generic — any session

  scope: "session"   after Complete (default)
         "exercise"  on that exercise's screen, once a set is logged
```

The most specific unused match wins — exercise beats idle beats generic — and
among equals the app rotates, taking turns with its own built-in card so the
same question never becomes wallpaper. An entry is spent once answered, and the
app always falls back to its own check-in when the bank is empty, so it works
whether or not the coach has ever run.

This is deliberately not the same thing as `coach.questions`: a question waits
in the Coach tab until you answer it, a staged check-in fires once, in context,
and is gone.

**The coach asks back.** It can write questions into `coach.questions`, which
appear as an answerable card at the top of the Coach tab and are nudged once
after a session. They are meant to be few and specific: it is told to ask at
most two or three, never to ask what the log already answers, to carry
unanswered ones forward unchanged, and to drop a question the moment it has been
answered. Your answers land in `app.checkins` and stay there.

The Coach tab carries a dot when a question is waiting or a brief has been
written since you last looked.

### The weekly review

A systemd user timer runs the coach every Sunday evening, whether or not you
think to ask it:

```
tools/weekly-review.sh          the run itself — a headless `claude -p` session
tools/liftlog-review.service    what runs it
tools/liftlog-review.timer      when (Sun 18:47, catching up a missed week)
```

Install by symlinking the two units into `~/.config/systemd/user/`, then:

```
systemctl --user daemon-reload
systemctl --user enable --now liftlog-review.timer
systemctl --user list-timers liftlog-review.timer   # confirm it is armed
journalctl --user -u liftlog-review -n 50           # read the last run
```

The session runs as the `workout-coach` agent with only `Read` and
`Bash(python3:*)` allowed — enough to run `coach-io.py` and nothing else. It
ends by printing a one-line summary, which the script turns into a desktop
notification. **A week with nothing to say sends no notification**: the coach is
told to write nothing when nothing has been logged since its last brief, and a
weekly "no news" is how notifications get switched off.

To stop it: `systemctl --user disable --now liftlog-review.timer`.

## Development

Plain HTML, CSS and JavaScript — no build step and no dependencies.

- `index.html` — the whole app
- `sw.js` — service worker (app-shell cache; **bump `CACHE` on every deploy**
  or installed copies keep serving the old version)
- `manifest.webmanifest` — PWA manifest
- `tools/fitnotes-to-liftlog.py` — converts a `.fitnotes` backup to a LiftLog
  backup file (standard library only)
- `tools/coach-io.py` — reads the synced state and writes back the coach block,
  refusing to touch anything the app owns
- `tools/weekly-review.sh` + `tools/liftlog-review.{service,timer}` — the
  scheduled weekly coach run and its systemd user timer

To test locally, serve the directory over HTTP (service workers don't run from
`file://`):

```
python3 -m http.server 8000
```
