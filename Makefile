output/paper_authors.csv:
	mkdir -p output
	bpython src/download_papers.py
csv: output/paper_authors.csv

working/no_header/paper_authors.csv: output/paper_authors.csv
	mkdir -p working/no_header
	tail +2 $^ > $@

all: csv

clean:
	rm -rf working
	rm -rf output
