
# The application uses Python 3.10+ type syntax; keep the runtime aligned with it.
FROM python:3.13-slim

# Set the working directory to /code
WORKDIR /code

# Copy the current directory contents into the container at /code
COPY ./requirements.txt /code/requirements.txt

# Install requirements.txt 
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the app directory
COPY ./app /code/app

# Create a non-root user for security (recommended by HF)
RUN useradd -m -u 1000 user
USER user
# Set home to the user's home directory
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user . $HOME/app

# Expose the API port used by local development and deployment.
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
