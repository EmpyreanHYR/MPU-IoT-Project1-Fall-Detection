# Makefile for IEEE Conference LaTeX Template
# 使用方法：
#   make        - 编译PDF
#   make clean  - 清理辅助文件
#   make view   - 编译并打开PDF

# 主文档文件名（不含.tex扩展名）
MAIN = fall_detection_final_report
SOURCES = $(MAIN).tex $(wildcard texfiles/*.tex) references.bib $(wildcard figs/*.png)

# LaTeX编译器选择
# 可选: pdflatex, xelatex, lualatex
LATEX = pdflatex

# 编译选项
LATEX_FLAGS = -interaction=nonstopmode -file-line-error

# PDF阅读器（根据操作系统调整）
# macOS: open
# Linux: xdg-open 或 evince
# Windows: start
VIEWER = open

# 默认目标：编译PDF
all: $(MAIN).pdf

# 编译PDF（包含BibTeX参考文献和交叉引用）
$(MAIN).pdf: $(SOURCES)
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex
	bibtex $(MAIN)
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex

# 使用BibTeX编译（如果使用.bib文件）
bib: $(MAIN).tex
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex
	bibtex $(MAIN)
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex
	$(LATEX) $(LATEX_FLAGS) $(MAIN).tex

# 清理辅助文件
clean:
	rm -f *.aux *.log *.out *.toc *.lof *.lot
	rm -f *.bbl *.blg *.bcf *.run.xml
	rm -f *.fls *.fdb_latexmk *.synctex.gz
	rm -f texfiles/*.aux

# 深度清理（包括PDF）
cleanall: clean
	rm -f $(MAIN).pdf

# 编译并打开PDF
view: $(MAIN).pdf
	$(VIEWER) $(MAIN).pdf

# 持续编译模式（使用latexmk）
watch:
	latexmk -pdf -pvc -interaction=nonstopmode $(MAIN).tex

.PHONY: all bib clean cleanall view watch
