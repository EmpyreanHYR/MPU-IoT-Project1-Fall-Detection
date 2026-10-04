# FallGuard project presentation

A fully English, static HTML presentation with 12 paged slides, English speaker notes and a separate Chinese speaker guide, a two-screen presenter console, and evidence and Q&A appendices. Prepared speech is approximately seven minutes, leaving time for transitions.

Open `index.html` in a browser, or serve the repository with `python3 -m http.server 8080` and visit `/docs/`. Scripts, styling, data and figures are bundled locally. No CDN, API credentials or inference service is needed.

## Controls

- **Paged view is the default**: only one slide is visible. Scroll or swipe to turn pages; expanded material scrolls inside its current page. A fresh scroll gesture at the page boundary advances the deck.
- **Contents**: jump to any slide or either appendix.
- **Chinese speaker guide**: open [`speaker-notes-zh.html`](speaker-notes-zh.html) or download [`speaker-notes-zh.md`](speaker-notes-zh.md).
- **Left / right arrows** or **Page Up / Page Down**: previous or next page. **Home / End**: first page or appendix.
- **Present / P**: enter a projection view with larger text, no toolbar and no speaker notes; Escape exits this view.
- **Presenter view**: open `presenter.html` on your laptop screen while the audience page stays on the projector. It shows bilingual notes, the next title, slide budgets and a pauseable total timer. Navigation and **B** (black screen) synchronize across the two pages. If the browser blocks the popup, allow it for this site. Both tabs must use the same browser and origin.
- **Space**: next slide.
- **N**: show/hide English speaker notes.
- **H**: enable/disable the text-line reading highlight. Table rows also highlight on hover or keyboard focus.
- **Full screen**: enter browser full screen.
- **Escape**: close the contents menu or an enlarged figure.
- **Print / PDF**: print the presentation using the browser.
- **Data appendix**: browse 1,853 archived aggregate rows. Current views exclude spatial-mask conditions with a normalization confound; a separate historical view and annotated CSV retain them with exclusion labels.

The presentation charts use means and sample standard deviations. Main, separate Le2i, external, robustness and archived protocols remain distinct. The hardware tables retain the no-output clip and distinguish clip recall from fall-interval detection. Cloud timing starts at the final source frame, not fall onset.

## Rebuild data

From the repository root:

```sh
python3 scripts/build_presentation_data.py
```

Inputs: `results/verification/verified_summary.csv` , `results/edge/summary.json`, and `results/alert-replay/summary.json`. The build writes `docs/assets/results-data.js` and `docs/assets/aggregate-results.csv`. It uses only Python's standard library.

## GitHub Pages

Publish branch `main`, directory `/docs`. The project presentation is available at:

- [Audience presentation](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/)
- [Presenter console](https://yaoronghuang.top/MPU-IoT-Project1-Fall-Detection/presenter.html)

The `empyreanhyr.github.io` address redirects to the account's existing custom domain; the redirect was checked on 2026-10-05. Use the canonical domain for both windows so cross-tab controls share an origin. This static site presents saved evidence. The Raspberry Pi and cloud backend are separate deployments.

## Rehearsal

Open the audience page first, click **Presenter view**, move the audience window to the projector and click **Present** or press **P**. Keep the console on your laptop. Select Chinese or English notes, start the timer, and use the console or arrow keys to advance. Prepared speech totals 420 seconds; transitions leave a target of 7–8 minutes. Evidence and Q&A appendices are outside this budget. Use **B** to pause the projected picture while answering a question. A full-screen browser window is optional.

To rebuild the bundled bilingual notes after editing the HTML or Chinese guide:

```sh
python3 scripts/build_presentation_notes.py
```

## Current content

The main robustness plot includes only frame removal and confidence noise. Fixed-rule confirmed-alert replay is a separate table on slide 6, using 12 primary test sequences. Raw predicted-event rates and confirmed-alert rates are labeled separately. English, Chinese and embedded speaker notes use the same claims and reserve a total of 420 seconds.
