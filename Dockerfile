FROM python:3.10-slim
ARG INSTALL_TYPE=main
# or all

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set the working directory
WORKDIR /app

# Install system dependencies
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip3 install poetry
RUN poetry config virtualenvs.create false

# Make Poetry available globally
# ENV PATH="/root/.local/bin:${PATH}"

# Copy the Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --only ${INSTALL_TYPE}

# Copy the rest of the application code
COPY . .

# Run migrations and collect static files
RUN python set_game_project/manage.py migrate
# RUN python set_game_project/manage.py collectstatic

# Expose the port Daphne will run on
EXPOSE 8000

# RUN chmod +x ./start_daphne.sh
WORKDIR /app/set_game_project
# Run the start_daphne.sh script to start Daphne
CMD ["./start_daphne.sh"]