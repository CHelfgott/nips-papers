import csv
import os
import re

# We are going to represent the affiliation of an author as a bitmap.
# Academia = 1, industry = 2, both = 3, neither/unidentified = 0.
ACADEMIA = 0x1
INDUSTRY = 0x2

academia_pattern = "(college|universit|dept|department|institute|ecole|\.edu\s)"
industry_pattern =\
    "(Co\.?\s|Inc\.?\s|\.com\s|Bell\s|Fujitsu|Xerox|IBM|Google|Apple|Microsoft)"

if not os.path.exists("output"):
  print("Paper database missing.")
  end
academia_cnt_by_year = dict()
industry_cnt_by_year = dict()
unknown_cnt_by_year = dict()
unaffiled_cnt_by_year = dict()
total_author_cnt_by_year = dict()
with open("output/paper_authors1.csv", "r") as table_fp:
  table_reader = csv.reader(table_fp, delimiter=',', quotechar='"')
  for line in table_reader:
    line_id, year, paper_id, title, citation_cnt, author_id, author_name,\
        a_affiliation, b_affiliation, abstract = line
    if line_id == "id": continue
    #print("Line Id:", line_id, " year: ", year, " Paper Id: ", paper_id)
    if not year in total_author_cnt_by_year:
      total_author_cnt_by_year[year] = 0.0
      academia_cnt_by_year[year] = 0.0
      industry_cnt_by_year[year] = 0.0
      unknown_cnt_by_year[year] = 0.0
      unaffiled_cnt_by_year[year] = 0.0
    total_author_cnt_by_year[year] += 1.0
    # a_affiliation is a substring taken from the textbox that the author's
    # name first appeared in; it may not include the actual affiliation if
    # the formatting is off.
    # b_affiliation is a substring taken from all text between the first
    # occurrance of the authors name and the first subsequent occurrance
    # of the word "Abstract" or the next authors name assuming that text
    # is non-trivial -- and is therefore likely to include too much,
    # specifically the affiliations of the other authors.
    assumed_affiliation = 0
    if len(a_affiliation) <= 12 and len(b_affiliation) <= 12:
      unaffiled_cnt_by_year[year] += 1.0
      unknown_cnt_by_year[year] += 1.0
      continue
    for affiliation_method_choice in [a_affiliation, b_affiliation]:
      if re.search(academia_pattern, affiliation_method_choice, re.IGNORECASE):
        assumed_affiliation |= ACADEMIA
      if re.search(industry_pattern, affiliation_method_choice, re.IGNORECASE):
        assumed_affiliation |= INDUSTRY
    if assumed_affiliation == 0:
      unknown_cnt_by_year[year] += 1.0
    elif assumed_affiliation == 1:
      academia_cnt_by_year[year] += 1.0
    elif assumed_affiliation == 2:
      industry_cnt_by_year[year] += 1.0
    elif assumed_affiliation == 3:
      academia_cnt_by_year[year] += 0.5
      industry_cnt_by_year[year] += 0.5

academic_percentages = list()
industry_percentages = list()
unaffiled_percentages = list()
for year, total_author_cnt in total_author_cnt_by_year.items():
  academia_cnt = academia_cnt_by_year[year]
  industry_cnt = industry_cnt_by_year[year]
  unknown_cnt = unknown_cnt_by_year[year]
  unaffiled_cnt = unaffiled_cnt_by_year[year]
  if abs(academia_cnt + industry_cnt + unknown_cnt - total_author_cnt) > 0.1:
    print("Total count inconsistent for ", year)
    continue
  print("NIPS author stats for ", year)
  print("Total authors: ", total_author_cnt)
  academic_percentages.append(academia_cnt * 100.0 / total_author_cnt)
  print("Academic percentage: ", academic_percentages[-1])
  industry_percentages.append(industry_cnt * 100.0 / total_author_cnt)
  print("Industry percentage: ", industry_percentages[-1])
  print("Unknown percentage: ", unknown_cnt * 100.0 / total_author_cnt)
  unaffiled_percentages.append(unaffiled_cnt * 100.0 / total_author_cnt)
print("Academic percentages over time: ", academic_percentages)
print("Industry percentages over time: ", industry_percentages)
print("\"Unaffiliated\" percentages over time: ", unaffiled_percentages)
