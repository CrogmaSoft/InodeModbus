# Use the official Python 3.9 image as the base
FROM python:3.9-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY . .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the command to run your application
CMD [ "python", "-u", "inode_modbus.py" ]
