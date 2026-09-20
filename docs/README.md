# FallGuard project presentation

A fully English, static HTML presentation with 12 talk sections, speaker notes, and a complete aggregate-data appendix.

Open `index.html` in a browser, or serve the repository with `python3 -m http.server 8080` and visit `/docs/`. Scripts, styling, data and figures are bundled locally. No CDN, API credentials or inference service is needed.

## Controls

- **Present**: show one talk section at a time; **Overview** restores the scrolling document.
- **Left / right arrows**: previous or next section.
- **N**: show/hide English speaker notes.
- **H**: enable/disable the text-line reading highlight. Table rows also highlight on hover or keyboard focus.
- **Full screen**: enter browser full screen.
- **Escape**: leave presentation mode, or close an enlarged figure.
- **Print / PDF**: print the presentation using the browser.
- **Data appendix**: filter all 1,853 aggregate rows, paginate, or display all matching rows; download the full CSV.

The presentation charts use means and sample standard deviations. Main, separate Le2i, external, robustness and archived protocols remain distinct. The hardware tables retain the no-output clip and distinguish clip recall from fall-interval detection. Cloud timing starts at the final source frame, not fall onset.

## Rebuild data

From the repository root:

```sh
python3 scripts/build_presentation_data.py
```

Inputs: `results/verification/verified_summary.csv` and `results/edge/summary.json`. The build writes `docs/assets/results-data.js` and `docs/assets/aggregate-results.csv`. It uses only Python's standard library.

## GitHub Pages

Publish branch `main`, directory `/docs`. Expected site:

https://empyreanhyr.github.io/MPU-IoT-Project1-Fall-Detection/

This is a static project presentation. The live Raspberry Pi services and cloud backend are separate deployments and are not exposed by GitHub Pages.
