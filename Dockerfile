# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables to prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies required by pygit2 and other packages
# libgit2-dev is the key dependency for building pygit2 from source if needed
# git is needed for some core functions that might shell out
# curl is needed for health checks
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libgit2-dev \
    git \
    pandoc \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash gitwrite

# Set the working directory in the container
WORKDIR /app

# Copy the poetry lock file and pyproject.toml file to leverage Docker cache
COPY poetry.lock pyproject.toml /app/

# Install poetry and project dependencies
# --no-interaction and --no-ansi are good for CI/CD environments
# virtualenvs.create false installs packages into the system site-packages, which is standard for Docker
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the application code into the container
COPY gitwrite_core/ /app/gitwrite_core/
COPY gitwrite_api/ /app/gitwrite_api/
COPY gitwrite_cli/ /app/gitwrite_cli/

# Create necessary directories
RUN mkdir -p /app/data/repositories /app/data/exports /app/logs \
    && chown -R gitwrite:gitwrite /app

# Switch to non-root user
USER gitwrite

# Expose the port the app runs on
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the API using uvicorn
# Use --host 0.0.0.0 to make it accessible from outside the container
CMD ["uvicorn", "gitwrite_api.main:app", "--host", "0.0.0.0", "--port", "8000"]