FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your backend code and the startup script
COPY . .

# Give the script execution permissions
RUN chmod +x start.sh

# Run the script when the container launches
CMD ["./start.sh"]