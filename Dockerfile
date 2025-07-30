FROM python:3.12-slim AS builder

# For 'build' stage, install poetry in a venv and use it to install dependencies

ENV POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_VENV=/opt/poetry-venv \
    POETRY_NO_INTERACTION=1

ENV PATH="${POETRY_VENV}/bin:$PATH"

RUN python3 -m venv $POETRY_VENV
RUN pip install -U pip setuptools \
	&& pip install poetry==${POETRY_VERSION}

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install -U pip setuptools && \
    poetry env use /app/.venv/bin/python && \
    poetry check && \
    poetry install --no-root --no-cache --without=dev


FROM python:3.12-slim AS runtime

# For 'run' stage, copy the dependencies in and install the package

WORKDIR /app

# Create data directory for SQLite
RUN mkdir data/

# Copy the virtual environment from the build stage
COPY --from=builder /app/.venv/ /app/.venv/
ENV PATH="/app/.venv/bin:$PATH"

# Copy the rest of the app code from the project
COPY pyproject.toml README.md run.py ./
COPY src ./src

# Dependencies are already installed in the venv, now just install the package
RUN pip install .

CMD ["python", "run.py"]
