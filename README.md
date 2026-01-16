# ResearchViewer
Arxiv dataset analyzer for CS 348 (Databases)

## Features

### Paper Analyzer
1) For each paper, get data on authors, citation number, keywords, journal, subject, and time
2) Allow sorting / analyzing to get metrics based on these units
3) Make charts showing change over certain metrics
4) See whole graph where edges are citations or author and colored by subject.

### Reccomender

1) Input recent papers you've read and get suggestions for similar papers (from the graph) by keeping small copy of read papers + likely neighbors

### Schema

1) Paper Table: Title, Abstract, Doi, Citations List (of DOIs), authors (IDs), keywords, journal, subject, submission time
2) Author Table: Author ID, Author name, Author Paper DOIs, H-Index?
3) Users: Username, Password, Read Papers, Subjects of interest, Candidate Next Papers