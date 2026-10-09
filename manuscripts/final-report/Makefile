# Build the report, group appendix, and Yaorong Huang personal contribution.
# make all builds all three; make report / contributions / huang builds one.
MAIN = fall_detection_final_report
CONTRIBUTIONS = personal_contributions
REPORT_SOURCES = $(MAIN).tex $(wildcard texfiles/*.tex) references.bib $(wildcard figs/*.pdf figs/*.png)
LATEXMK = latexmk
LATEX_FLAGS = -pdf -interaction=nonstopmode -halt-on-error -file-line-error
VIEWER = open

all: report contributions huang

report: G7_Final_Report.pdf

contributions: G7_Personal_Contributions.pdf

huang: G7_Yaorong_Huang_Contribution.pdf

$(MAIN).pdf: $(REPORT_SOURCES)
	$(LATEXMK) $(LATEX_FLAGS) $(MAIN).tex

$(CONTRIBUTIONS).pdf: $(CONTRIBUTIONS).tex
	$(LATEXMK) $(LATEX_FLAGS) $(CONTRIBUTIONS).tex

G7_Final_Report.pdf: $(MAIN).pdf
	cp $(MAIN).pdf $@

G7_Personal_Contributions.pdf: $(CONTRIBUTIONS).pdf
	cp $(CONTRIBUTIONS).pdf $@

yaorong_huang_contribution.pdf: yaorong_huang_contribution.tex
	$(LATEXMK) $(LATEX_FLAGS) yaorong_huang_contribution.tex

G7_Yaorong_Huang_Contribution.pdf: yaorong_huang_contribution.pdf
	cp yaorong_huang_contribution.pdf $@

bib: report

clean:
	$(LATEXMK) -c $(MAIN).tex $(CONTRIBUTIONS).tex yaorong_huang_contribution.tex

cleanall: clean
	rm -f $(MAIN).pdf $(CONTRIBUTIONS).pdf yaorong_huang_contribution.pdf G7_Final_Report.pdf G7_Personal_Contributions.pdf G7_Yaorong_Huang_Contribution.pdf

view: report
	$(VIEWER) G7_Final_Report.pdf

watch:
	$(LATEXMK) -pdf -pvc -interaction=nonstopmode $(MAIN).tex

.PHONY: all report contributions huang bib clean cleanall view watch
