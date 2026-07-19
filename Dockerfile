# Multi-stage build: React frontend + Flask backend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./backend/app/static/

WORKDIR /app/backend
RUN mkdir -p uploads

ENV FLASK_ENV=production
ENV UPLOAD_FOLDER=/app/backend/uploads
ENV DATABASE_URL=sqlite:////app/backend/traqcheck.db

EXPOSE 5000

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120"]
