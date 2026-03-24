# ResearchViewer

A web application for exploring and analyzing research papers from arXiv. Built with Flask, DuckDB, and React.

![API Tests](https://github.com/ShayManor/ResearchViewer/actions/workflows/test-api.yml/badge.svg)

## Overview

ResearchViewer helps researchers discover, organize, and understand academic papers through:
- **Search & Discovery**: Filter 2.9M papers by keywords, authors, topics, citations, and dates
- **Topic Analysis**: Explore 11K microtopics generated through clustering and semantic analysis
- **Personal Library**: Track reading lists, mark papers as read, and link your author profile
- **Recommendations**: Get personalized paper suggestions based on your reading history
- **Analytics**: View trends, citation patterns, and velocity metrics across fields

## Architecture

### Backend
- **Framework**: Flask with Gunicorn
- **Database**: DuckDB (2.9M papers, 1.7M authors, 11K microtopics)
- **Authentication**: Firebase Auth with Google OAuth
- **Caching**: Redis for caching APIs
- **API**: RESTful JSON endpoints (see [API.md](API.md))

### Frontend
- **Framework**: React with TypeScript
- **Build**: Vite
- **UI**: TailwindCSS
- **Charts**: Recharts for visualizations
- **State**: React Context for auth and global state

### Data Pipeline
Papers are sourced from arXiv metadata, enriched with:
- Citation data from OpenAlex
- Custom topic classifications (domains, fields, topics, microtopics)
- Author information and calculated h-indices
- Semantic clustering for microtopic discovery

## Database Schema

### Core Tables
- **papers** (2.9M rows): arXiv papers with metadata, citations, and topic classifications
- **authors** (1.7M rows): Author profiles with h-index and publication lists
- **microtopics** (11K rows): Fine-grained topics discovered through clustering
- **paper_microtopics** (5.2M rows): Many-to-many mapping with relevance scores

### User Tables
- **users**: Firebase-authenticated user profiles
- **user_reading_list**: Papers saved to read
- **user_read_history**: Papers marked as read with timestamps
- **user_publications**: User-entered publications for tracking personal work

## Deployment

The application runs in Docker with automated CI/CD:

1. **Build**: GitHub Actions builds the frontend and creates a Docker image
2. **Push**: Image is pushed to GitHub Container Registry
3. **Deploy**: Self-hosted runner pulls the image and restarts the container
4. **Secrets**: Firebase credentials are mounted from the host filesystem

```bash
# Local development
python -m src.main  # Backend on :8080
cd frontend && npm run dev  # Frontend on :3000

# Production (via GitHub Actions)
git push origin main  # Triggers build and deploy
```

## Configuration

### Backend
- `FIREBASE_CREDENTIALS_PATH`: Path to Firebase service account JSON
- `DATABASE_PATH`: Path to main DuckDB database (papers, authors, topics)
- `USER_DB_PATH`: Path to user DuckDB database (separate for user data)

### Frontend
Environment variables (prefixed with `VITE_`):
- `VITE_FIREBASE_API_KEY`: Firebase web API key
- `VITE_FIREBASE_AUTH_DOMAIN`: Firebase auth domain
- `VITE_FIREBASE_PROJECT_ID`: Firebase project ID
- `VITE_FIREBASE_STORAGE_BUCKET`: Firebase storage bucket
- `VITE_FIREBASE_MESSAGING_SENDER_ID`: Firebase messaging sender ID
- `VITE_FIREBASE_APP_ID`: Firebase app ID
- `VITE_API_URL`: Backend API URL (empty for same-origin)

## Performance

The backend handles 600+ req/sec on localhost for simple queries. Most complex queries (topic analytics, recommendations) complete in <200ms.
