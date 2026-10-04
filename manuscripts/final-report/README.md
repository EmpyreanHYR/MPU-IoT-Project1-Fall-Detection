# Final project report

Main source: `fall_detection_final_report.tex`

Content synchronized on 2026-10-05 with the canonical course report. The repository resource link is a separate block after the keywords and before the introduction. All five authors share one IEEE affiliation, with Yaorong Huang listed first. Figures use PNG copies of the canonical vector figures. The current A4 report compiles to 10 pages; the standalone `personal_contributions.tex` appendix records Yaorong Huang’s reported code, writing and presentation work. Other members have name-and-TBD entries to complete. Meeting records and Turnitin still require actual team input.

Compile with:

```bash
make
```

The generated `fall_detection_final_report.pdf` and auxiliary LaTeX files are ignored by Git.

Reported aggregate values are linked from [`RESULTS_PROVENANCE.md`](RESULTS_PROVENANCE.md) to the repository's compact [`results/`](../../results/) evidence.

Compile the standalone personal appendix independently:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error personal_contributions.tex
```

The appendix is separate from the ten-page main report.
