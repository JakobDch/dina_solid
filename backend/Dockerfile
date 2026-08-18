FROM python:3.12-slim

# build-essential and libpq-dev are needed to build psycopg; curl is used by
# the container health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Install dependencies first so this layer is cached across source changes.
COPY pyproject.toml /code/
RUN pip install --no-cache-dir .

COPY ./app /code/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
