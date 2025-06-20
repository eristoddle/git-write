# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the poetry lock file and pyproject.toml file
COPY poetry.lock pyproject.toml /app/

# Install poetry
RUN pip install poetry

# Install project dependencies
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the application code
COPY gitwrite_core/ /app/gitwrite_core/
COPY gitwrite_api/ /app/gitwrite_api/

# Command to run the API using uvicorn
CMD ["uvicorn", "gitwrite_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
