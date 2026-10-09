# Final report and contribution appendix

Updated: 9 October 2026.

- `fall_detection_final_report.tex`: main A4 IEEE two-column report, with figures and references, within the course's ten-page limit.
- `yaorong_huang_contribution.tex`: standalone two-page personal copy of Yaorong Huang’s expanded implementation, integration and reporting work.
- `personal_contributions.tex`: independent A4 IEEE two-column **Appendix A**, consolidating the five members' individual work, encountered problems, attempted solutions, collaboration and reflection.

The contribution appendix is submitted alongside the main report and is compiled
separately. It is not included with `\input` in the main document.

```sh
make
```

This builds `fall_detection_final_report.pdf`, `personal_contributions.pdf`, and the standalone `yaorong_huang_contribution.pdf`.
The [reviewed PDFs](../../docs/downloads/) and the [submission entry](../../SUBMISSION.md)
are the handover copies. The main text emphasizes the evaluated advantages of
MaskedBiMamba and the complete edge-to-cloud system. Evaluation scope and next
steps are stated once; the experiment results and model ranking are retained.

[RESULTS_PROVENANCE.md](RESULTS_PROVENANCE.md) links the numerical evidence to
[results](../../results/). Sources are synchronized with the canonical local
course report. Vector PDF figures and the required PNG screenshots are included for compilation.
