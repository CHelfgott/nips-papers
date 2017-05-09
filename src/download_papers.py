from bs4 import BeautifulSoup
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice, TagExtractor
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
import json
import os
import pandas as pd
import re
import requests
import subprocess
import sys

# Extracts last name from "First_Name Middle_Name Last_Name" or "Last_Name, First_Name".
# Will return the wrong thing for names ending in "the 3rd", "Esq.", etc.
# It will also fail for Chinese and Japanese names in the traditional order.
def get_last_name(name):
  clean_name = re.sub("[^A-Za-z0-9 ,\w]", "", name)
  lastname_block = re.search("^(\w*)\s*(Jr\.?|Sr\.?)?,\s*\w*", clean_name)
  if not lastname_block:
    lastname_block = re.search("\s*(\w*)\s*(Jr\.?|Sr\.?)?$", clean_name)
  if lastname_block:
    return lastname_block.group(1)
  else:
    return ""

# Extracts text from pdf; also attempts to extract author affiliations from
# the text blocks containing the authors' names.
def text_from_pdf(pdf_path, authors):
  extracted_text = ""
  affiliations = dict()
  author_lastnames = set()
  author_lastname_pattern = ""
  for author in authors:
    lastname = get_last_name(author[1])
    print("Lastname:", lastname)
    author_lastnames.add(lastname)
    author_lastname_pattern += lastname + "\s*,?\s*|"
  author_lastname_pattern = "(" + author_lastname_pattern[:-1] + ")"
  print("Author lastname pattern:", author_lastname_pattern)
  # Create a PDF parser object associated with the file object.
  infp = open(pdf_path, "rb")
  parser = PDFParser(infp)
  # Create a PDF document object that stores the document structure.
  # Supply the password for initialization.
  document = PDFDocument(parser)
  # Set parameters for analysis.
  laparams = LAParams()
  # Create a PDF page aggregator object.
  rsrcmgr = PDFResourceManager(caching=True)
  device = PDFPageAggregator(rsrcmgr, laparams=laparams)
  interpreter = PDFPageInterpreter(rsrcmgr, device)
  for page in PDFPage.create_pages(document):
    interpreter.process_page(page)
    # receive the LTPage object for the page.
    layout = device.get_result()
    for lt_obj in layout:
      if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
        tmp_text = re.sub("[^A-Za-z0-9 ,\s\.@]", "", lt_obj.get_text())
        author_count = 0
        for lastname in author_lastnames:
          if re.search(lastname, tmp_text): author_count += 1
        if author_count > 0:
          print("Author text block: ", tmp_text)
          tmp_pattern = author_lastname_pattern + "{" + str(author_count) + "}(.*)$"
          affiliation_block = re.search(tmp_pattern, tmp_text, re.DOTALL)
          if affiliation_block:
            print("Groups: ", affiliation_block.groups())
            for lastname in author_lastnames:
              if (not lastname in affiliations) and re.search(lastname, tmp_text):
                if (len(affiliation_block.groups()) > author_count):
                  affiliations[lastname] = affiliation_block.group(author_count + 1)
                else:
                  affiliations[lastname] = tmp_text
        extracted_text += tmp_text + "\n"
    infp.close()
    device.close()
    if os.path.exists("working/temp"):
      os.remove("working/temp")
    outfp = open(temp_path, "w", encoding="utf-8")
    outfp.write(extracted_text)
    outfp.close()
    #os.remove(temp_path)
    return (extracted_text, affiliations)

# We are going to extract the full text from one authors last name to the next authors
# name as an "affiliation".  This may include e.g. the next author's first name if the name
# differs from NIPS paper description to the actual paper.  If multiple authors appear
# only separated by commas and whitespace, they will all be given the affiliation of the last
# author.
def get_author_affiliations(title, author_list, paper_text):
  print("Title: ", title)
  title_pattern = re.sub("\s", "\\s*", title)
  title_pattern = re.sub("-|\+", ".?", title_pattern)
  print("Title Pattern: ", title_pattern)
  affiliations = dict()
  print(author_list)
  if not author_list:
    return affiliations
  # Find the block of text between the title and the work "Abstract".
  # This should contain the authors + their affiliations.
  re_flags = re.IGNORECASE | re.DOTALL
  print("Text: ", paper_text[0:300])
  aff_str = ""
  author_aff_block = re.search(title_pattern + "\s*(.*)\s*abstract", paper_text, re_flags)
  if author_aff_block:
    aff_str = author_aff_block.group(1)
  else:
    author_aff_block = re.search(title_pattern + "\s*(.*)", paper_text, re_flags)
  if author_aff_block:
    aff_str = author_aff_block.group(1)[0:300]
  else:
    for author in author_list:
      author_lastname = get_last_name(author[1])
      affiliations[author_lastname] = ""
    return affiliations
  print("Affiliation Block: ", aff_str)
  affiliation = ""
  terminator_pattern = "$"
  for author in reversed(author_list):
    author_lastname = get_last_name(author[1])
    print("Last Name: ", author_lastname)
    re_pattern = author_lastname + ",?\s*(.*)\s*" + terminator_pattern
    print("Pattern: ", re_pattern)
    temp_aff_block = re.search(re_pattern, aff_str, re_flags)
    if not temp_aff_block:
      temp_aff_block = re.search(author_lastname + ",?\s*(.*)\s*$", aff_str, re_flags)
    if temp_aff_block:
      affiliation = temp_aff_block.group(1)
      affiliations[author_lastname] = affiliation
    print("Affiliation: ", affiliation)
    terminator_pattern = re.sub("-", ".?", "[" + author[1] + "|" + author_lastname + "]")
    terminator_pattern = re.sub("\\\\", "", terminator_pattern)

  return affiliations

base_url  = "http://papers.nips.cc"

index_urls = {1987: "https://papers.nips.cc/book/neural-information-processing-systems-1987"}
for i in range(1, 30):
  year = i+1987
  index_urls[year] = "http://papers.nips.cc/book/advances-in-neural-information-processing-systems-%d-%d" % (i, year)

nips_authors = set()
papers = list()
paper_authors = list()

re_flags = re.IGNORECASE | re.DOTALL

for year in sorted(index_urls.keys()):
  index_url = index_urls[year]
  index_html_path = os.path.join("working", "html", str(year)+".html")

  if not os.path.exists(index_html_path):
    r = requests.get(index_url)
    if not os.path.exists(os.path.dirname(index_html_path)):
      os.makedirs(os.path.dirname(index_html_path))
    with open(index_html_path, "wb") as index_html_file:
      index_html_file.write(r.content)
  with open(index_html_path, "rb") as f:
    html_content = f.read()
  soup = BeautifulSoup(html_content, "lxml")
  paper_links = [link for link in soup.find_all('a') if link["href"][:7]=="/paper/"]
  print("%d Papers Found" % len(paper_links))

  temp_path = os.path.join("working", "temp.txt")

  bad_paper_ids = ("2646", "3677", "4281", "4418", "5820")

  for link in paper_links:
    paper_title = link.contents[0]
    info_link = base_url + link["href"]
    bibtex_link = info_link + "/bibtex"
    print("Info link: ", info_link, "; BibTeX link: ", bibtex_link)
    pdf_link = info_link + ".pdf"
    pdf_name = link["href"][7:] + ".pdf"
    pdf_path = os.path.join("working", "pdfs", str(year), pdf_name)
    paper_id = re.findall(r"^(\d+)-", pdf_name)[0]
    if paper_id in bad_paper_ids: continue  # These papers break things.
    print(year, " ", paper_id) #paper_title.encode('ascii', 'namereplace'))
    if not os.path.exists(pdf_path):
      pdf = requests.get(pdf_link)
      if not os.path.exists(os.path.dirname(pdf_path)):
        os.makedirs(os.path.dirname(pdf_path))
      pdf_file = open(pdf_path, "wb")
      pdf_file.write(pdf.content)
      pdf_file.close()

    paper_info_html_path = os.path.join("working", "html", str(year), str(paper_id)+".html")
    if not os.path.exists(paper_info_html_path):
      r = requests.get(info_link)
      if not os.path.exists(os.path.dirname(paper_info_html_path)):
        os.makedirs(os.path.dirname(paper_info_html_path))
      with open(paper_info_html_path, "wb") as f:
        f.write(r.content)
    with open(paper_info_html_path, "rb") as f:
      html_content = f.read()
    paper_soup = BeautifulSoup(html_content, "lxml")
    try:
      abstract = paper_soup.find('p', attrs={"class": "abstract"}).contents[0]
    except:
      print("Abstract not found %s" % paper_title.encode("ascii", "replace"))
      abstract = ""
    authors = [(re.findall(r"-(\d+)$", author.contents[0]["href"])[0],
                author.contents[0].contents[0])
               for author in paper_soup.find_all('li', attrs={"class": "author"})]
    with open(pdf_path, "rb") as f:
      if f.read(15)==b"<!DOCTYPE html>":
        print("PDF MISSING")
        continue

    try:
      paper_text, alpha_affiliations = text_from_pdf(pdf_path, authors)
    except:
      print("Could not extract paper text from PDF %s" %
            paper_title.encode("ascii", "replace"))

    try:
      beta_affiliations = get_author_affiliations(paper_title, authors, paper_text)
    except:
      print("Could not extract author affiliations from text %s" %
            paper_title.encode("ascii", "replace"))

    for author in authors:
      alpha_affiliation = ""
      beta_affiliation = ""
      author_lastname = get_last_name(author[1])
      nips_authors.add(author)
      if author_lastname in alpha_affiliations:
        alpha_affiliation = alpha_affiliations[author_lastname]
      if author_lastname in beta_affiliations:
        beta_affiliation = beta_affiliations[author_lastname]
      paper_authors.append([len(paper_authors)+1, paper_id, author[0], alpha_affiliation, beta_affiliation])
      print("Author num: ", author[0], ", Author name: ", author[1])
      event_types = [h.contents[0][23:] for h in paper_soup.find_all('h3') if h.contents[0][:22]=="Conference Event Type:"]
      if len(event_types) != 1:
        #print(event_types)
        #print([h.contents for h in paper_soup.find_all('h3')].__str__().encode("ascii", "replace"))
        #raise Exception("Bad Event Data")
        event_type = ""
      else:
        event_type = event_types[0]
      papers.append([paper_id, year, paper_title, event_type, pdf_name, abstract, paper_text])

if not os.path.exists("output"):
  os.makedirs("output")

pd.DataFrame(list(nips_authors), columns=["id","name"]).sort_values(by="id").to_csv("output/authors.csv", index=False)
pd.DataFrame(papers, columns=["id", "year", "title", "event_type", "pdf_name", "abstract", "paper_text"]).sort_values(by="id").to_csv("output/papers.csv", index=False)
pd.DataFrame(paper_authors, columns=["id", "paper_id", "author_id", "a_affiliation", "b_affiliation"]).sort_values(by="id").to_csv("output/paper_authors.csv", index=False)
