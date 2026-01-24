# CLAUDE.md

## Working relationship
- You can push back on ideas-this can lead to better documentation. Cite sources and explain your reasoning when you do so
- ALWAYS ask for clarification rather than making assumptions
- NEVER lie, guess, or make up information

## Project context
- Audio2 is a personal music streaming API and web application
- Backend: FastAPI (Python) + PostgreSQL
- Frontend: React/TypeScript + Vite
- Integrations: Spotify, Last.fm, YouTube Data API

## Content strategy
- Document just enough for user success - not too much, not too little
- Prioritize accuracy and usability of information
- Make content evergreen when possible
- Search for existing information before adding new changes. Avoid duplication
- Check existing patterns for consistency
- Start by making the smallest reasonable changes

## Git workflow
- Create a new branch for significant changes when no clear branch exists
- Commit frequently throughout development
- NEVER skip or disable pre-commit hooks (flake8 validation)
- Ask how to handle uncommitted changes before starting

## Do not
- Skip frontmatter on any documentation files
- Use absolute URLs for internal links
- Include untested code examples
- Make assumptions - always ask for clarification
