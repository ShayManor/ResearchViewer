# ResearchViewer
Arxiv dataset analyzer for CS 348 (Databases)

## Features

### Paper Analyzer
1) For each paper (2.1 million records), get data on authors, citation number, keywords, journal, subject, and time
2) Allow sorting / analyzing to get metrics based on these units
3) Make charts showing change over certain metrics
4) See whole graph where edges are citations or author and colored by subject.

### Recommender

1) Input recent papers you've read and get suggestions for similar papers (from the graph) by keeping small copy of read papers + likely neighbors

### Schema

1) Paper Table: Title, Abstract, Doi, Citations List (of DOIs), authors (IDs), keywords, journal, subject, submission time
2) Author Table: Author ID, Author name, Author Paper DOIs, H-Index?
3) Users: Username, Password, Read Papers, Subjects of interest, Candidate Next Papers

### Services

**Add Paper:**

Input Title, link, DOI, Authors, citations, keywords, subject, title and added to registry

**Generate New Paper Info:**

Used in Add Paper and as separate option.\
Input DOI and authors, citations, keywords, subject, title are automatically populated

**Get Paper:**

Returns DOI, Authors, Citations, Keywords, Subject, Title

**Update Paper:**

Give DOI and update field, updates this field in database.

**Add Author:**

Input Author ID (OpenAlex or ORCID url), Name, Optional link to website, Optional current title, Optional Image

**Update Author:**

Input Author ID and field to update and changes that field

**Generate New Author Info:**

Input Author ID (OpenAlex or ORCID) and gets their name as well as other details

**Get Author (ID):**

Input author ID and gets details

**Get Author (Name):**

Input (complete or incomplete) author name and gets all candidate author details

### API Endpoints

**Papers**

`GET /api/papers`
Get all papers with optional filters (subject, journal, date range, keyword). Supports pagination and sorting.

`GET /api/papers/<doi>`
Get single paper by DOI. Returns title, abstract, authors, citations, keywords, journal, subject, submission time.

`POST /api/papers`
Add new paper. Input: title, doi, authors, citations, keywords, journal, subject, submission_time.

`PUT /api/papers/<doi>`
Update existing paper by DOI. Input: fields to update.

`DELETE /api/papers/<doi>`
Remove paper from database.

`POST /api/papers/generate`
Auto-populate paper info from DOI. Input: doi. Returns: title, authors, citations, keywords, subject.

`GET /api/papers/<doi>/citations`
Get all papers that cite this paper.

`GET /api/papers/<doi>/references`
Get all papers this paper cites.

**Authors**

`GET /api/authors`
Get all authors with optional filters (name search, subject). Supports pagination.

`GET /api/authors/<author_id>`
Get author by OpenAlex/ORCID ID. Returns: name, papers, h-index, website, title, image.

`GET /api/authors/search?name=<query>`
Search authors by partial name match. Returns list of candidates.

`POST /api/authors`
Add new author. Input: author_id, name, website (optional), title (optional), image (optional).

`PUT /api/authors/<author_id>`
Update existing author. Input: fields to update.

`DELETE /api/authors/<author_id>`
Remove author from database.

`POST /api/authors/generate`
Auto-populate author info from ID. Input: author_id (OpenAlex/ORCID). Returns: name, papers, h-index.

**Users**

`POST /api/users/register`
Create new user. Input: username, password.

`POST /api/users/login`
Authenticate user. Input: username, password. Returns: session token.

`GET /api/users/me`
Get current user profile. Returns: username, read_papers, subjects_of_interest, candidate_papers.

`PUT /api/users/me`
Update user preferences. Input: subjects_of_interest.

`POST /api/users/me/read`
Add paper to read list. Input: doi.

`DELETE /api/users/me/read/<doi>`
Remove paper from read list.

`GET /api/users/me/recommendations`
Get recommended papers based on read history and interests.

**Analytics**

`GET /api/analytics/papers/over-time`
Get paper counts over time. Query params: group_by (year/month), subject (optional).

`GET /api/analytics/citations/distribution`
Get citation count distribution across papers.

`GET /api/analytics/subjects`
Get paper counts by subject.

`GET /api/analytics/authors/top`
Get top authors by h-index or paper count.

`GET /api/analytics/graph`
Get citation/author graph data for visualization. Query params: subject (optional), limit.

**Users**

`POST /api/users/register`
Create new user. Input: username, password.

`POST /api/users/login`
Authenticate user. Input: username, password. Returns: session token.

`GET /api/users/<user_id>`
Get user profile. Returns: username, read_papers, subjects_of_interest.

`DELETE /api/users/<user_id>`
Remove user and all associated data.

`POST /api/users/<user_id>/subjects`
Add subject to user interests. Input: subject.

`DELETE /api/users/<user_id>/subjects/<subject>`
Remove subject from user interests.

`POST /api/users/<user_id>/read`
Add paper to read list. Input: doi.

`DELETE /api/users/<user_id>/read/<doi>`
Remove paper from read list.

`GET /api/users/<user_id>/recommendations`
Get recommended papers based on read history and subjects. Returns papers that are:
1. Cited by or citing papers the user has read (graph neighbors)
2. In subjects the user is interested in
3. Highly cited within those subjects

Query params: limit (default 10).