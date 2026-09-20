# FallGuard project presentation

A fully English, static HTML presentation with 12 paged slides, English speaker notes and a separate Chinese speaker guide, and a complete aggregate-data appendix.

Open `index.html` in a browser, or serve the repository with `python3 -m http.server 8080` and visit `/docs/`. Scripts, styling, data and figures are bundled locally. No CDN, API credentials or inference service is needed.

## Controls

- **Paged view is the default**: only one slide is visible. Scroll or swipe to turn pages; expanded material scrolls inside its current page. A fresh scroll gesture at the page boundary advances the deck.
- **Contents**: jump to any slide or the data appendix.
- **Chinese speaker guide**: open [`speaker-notes-zh.html`](speaker-notes-zh.html) or download [`speaker-notes-zh.md`](speaker-notes-zh.md).
- **Left / right arrows** or **Page Up / Page Down**: previous or next page. **Home / End**: first page or appendix.
- **N**: show/hide English speaker notes.
- **H**: enable/disable the text-line reading highlight. Table rows also highlight on hover or keyboard focus.
- **Full screen**: enter browser full screen.
- **Escape**: close the contents menu or an enlarged figure.
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

Publish branch `main`, directory `/docs`. The repository's default Pages address is:

https://empyreanhyr.github.io/MPU-IoT-Project1-Fall-Detection/

This repository has no custom domain configured. GitHub Pages currently redirects this address to the account's existing user-site domain, `yaoronghuang.top`. GitHub's [custom-domain inheritance rule](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages) applies to project sites. Keeping this project on the same account's `github.io` address requires removing the user site's custom-domain binding, which also affects the personal website. That account-level change has not been made.

This is a static project presentation. The live Raspberry Pi services and cloud backend are separate deployments and are not exposed by GitHub Pages. HTTPS is enforced.
