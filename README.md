# LiftLog

An offline-first workout logger with automatic weight and rep progression
suggestions. Built as a companion to FitNotes — it imports your FitNotes
export and carries on from there, adding the one thing FitNotes doesn't do:
telling you what to load next.

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
increment, cadence and rep range, under **Progression settings**.

Suggestions are computed from the limiting set at the top weight of your last
session, so drop sets and back-off sets don't skew them.

## Setup

1. Open the site and add it to your home screen (Chrome: ⋮ → *Add to home
   screen*). It then runs standalone and works with no connection at all.
2. In FitNotes: **Settings → Backup → Export**, and put the CSV somewhere you
   can reach from the phone.
3. In LiftLog: **Data → Import CSV**. This brings across every exercise, its
   category, and your full set history.
4. Rebuild your routines under **Routines** (FitNotes' CSV export contains
   logged sets only, not routines).

## Data

Everything lives in this browser on this device — there is no account, no
server, and nothing is transmitted. That also means clearing site data wipes
it, so use **Data → Download CSV** now and then. The export is in FitNotes'
own CSV format, so it round-trips back into FitNotes or into the Ledger
coaching app.

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

To test locally, serve the directory over HTTP (service workers don't run from
`file://`):

```
python3 -m http.server 8000
```
