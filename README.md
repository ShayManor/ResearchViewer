# ResearchViewer

A web application for exploring and analyzing research papers from arXiv.

[![API Tests](https://github.com/ShayManor/ResearchViewer/actions/workflows/test-api.yml/badge.svg?branch=main)](https://github.com/ShayManor/ResearchViewer/actions/workflows/test-api.yml)
[![Site Health](https://github.com/ShayManor/ResearchViewer/actions/workflows/health-check.yml/badge.svg?branch=main)](https://github.com/ShayManor/ResearchViewer/actions/workflows/health-check.yml)

**Live Site**: [researchviewer.org](https://researchviewer.org) | **API**: [researchviewer.org/api](https://researchviewer.org/api/)

## Features

- **Search & Discovery**: Filter 2.9M papers by keywords, authors, topics, citations, and dates
- **Topic Analysis**: Explore 11K microtopics generated through clustering and semantic analysis
- **Personal Library**: Track reading lists, mark papers as read, and link your author profile
- **Recommendations**: Get personalized paper suggestions based on your reading history
- **Analytics**: View trends, citation patterns, and velocity metrics across fields

## Tech Stack

**Backend**: Flask + Gunicorn, DuckDB (2.9M papers, 1.7M authors, 11K microtopics), Firebase Auth, Redis caching

**Frontend**: React + TypeScript, Vite, TailwindCSS, Recharts

**Data**: arXiv metadata enriched with OpenAlex citations, custom topic classifications, and semantic clustering

## Database

**Core Tables**: papers (2.9M), authors (1.7M), microtopics (11K), paper_microtopics (5.2M)

**User Tables**: users, reading lists, read history, publications

## Development

```bash
# Backend (runs on :8080)
python -m src.main

# Frontend (runs on :3000)
cd frontend && npm run dev
```

## Deployment

Docker deployment with GitHub Actions CI/CD:
1. Push to `main` triggers build
2. Image pushed to GitHub Container Registry
3. Self-hosted runner pulls and restarts container
