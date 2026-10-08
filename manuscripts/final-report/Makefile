# Build the report and standalone IEEE contribution appendix.
# make / make all: both documents and submission-named PDF copies.
# make report: main report only; make contributions: standalone appendix only.
MAIN = fall_detection_final_report
CONTRIBUTIONS = personal_contributions
REPORT_SOURCES = $(MAIN).tex $(wildcard texfiles/*.tex) references.bib $(wildcard figs/*.pdf figs/*.png)
LATEXMK = latexmk
LATEX_FLAGS = -pdf -interaction=nonstopmode -halt-on-error -file-line-error
VIEWER = open

all: report contributions

report: G7_Final_Report.pdf

contributions: G7_Personal_Contributions.pdf

$(MAIN).pdf: $(REPORT_SOURCES)
	$(LATEXMK) $(LATEX_FLAGS) $(MAIN).tex

$(CONTRIBUTIONS).pdf: $(CONTRIBUTIONS).tex
	$(LATEXMK) $(LATEX_FLAGS) $(CONTRIBUTIONS).tex

G7_Final_Report.pdf: $(MAIN).pdf
	cp $(MAIN).pdf $@

G7_Personal_Contributions.pdf: $(CONTRIBUTIONS).pdf
	cp $(CONTRIBUTIONS).pdf $@

bib: report

clean:
	$(LATEXMK) -c $(MAIN).tex $(CONTRIBUTIONS).tex

cleanall: clean
	rm -f $(MAIN).pdf $(CONTRIBUTIONS).pdf G7_Final_Report.pdf G7_Personal_Contributions.pdf

view: report
	$(VIEWER) G7_Final_Report.pdf

watch:
	$(LATEXMK) -pdf -pvc -interaction=nonstopmode $(MAIN).tex

.PHONY: all report contributions bib clean cleanall view watch
