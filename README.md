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
      Set          weight × reps — weight may be negative

Session      one performance of a Workout. Starts when you log the first
             set, ends when you tap Complete, and owns the sets between.
```

Reordering exercises during a session is saved back to the **workout**, so the
order sticks next time. Skipping one — a broken machine, a day you don't feel
like it — applies to **that session only** and leaves the workout alone.

## Why

FitNotes is a good logger but has no progression logic — you decide the
weight every session yourself. LiftLog keeps FitNotes' fast, offline,
no-account approach and puts a suggested next weight × reps at the top of
every exercise screen.

## How progression works

Two rules, picked per exercise:

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

FitNotes also tracks duration and distance work — planks, farmers walks,
cardio. LiftLog only models weight × reps, so those sets aren't carried over.
The exercises themselves are, since routines reference them, and they say so
on their own screen instead of offering a meaningless suggestion.

## Data

Everything lives in this browser on this device — there is no account, no
server, and nothing is transmitted. That also means clearing site data wipes
it, so export now and then:

- **Data → Backup file → Download** — the complete picture, including routines
  and progression settings. This is the one to keep.
- **Data → Download CSV** — sets only, in FitNotes' own format, for feeding the
  Ledger coaching app or moving back to FitNotes.

## Coach suggestions

The `coachSuggestions` JSON from the Ledger app can be pasted under
**Data → Coach suggestions**. Those override the built-in calculation and show
as "Coach suggests", with the auto-calculated figure still visible underneath.

## Development

Plain HTML, CSS and JavaScript — no build step and no dependencies.

- `index.html` — the whole app
- `sw.js` — service worker (app-shell cache; **bump `CACHE` on every deploy**
  or installed copies keep serving the old version)
- `manifest.webmanifest` — PWA manifest
- `tools/fitnotes-to-liftlog.py` — converts a `.fitnotes` backup to a LiftLog
  backup file (standard library only)

To test locally, serve the directory over HTTP (service workers don't run from
`file://`):

```
python3 -m http.server 8000
```
