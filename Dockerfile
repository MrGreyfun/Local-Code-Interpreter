# Use an official Python runtime as a parent image
FROM python:3.9.16

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements_full.txt 
# Copy the config.example.json to src/config.json
RUN cp /app/config_example/config.example.json /app/src/config.json

# change config.json API_KEY value to empty string
# RUN sed -i 's/\"API_KEY\": \".*\"/\"API_KEY\": \"\"/' /app/src/config.json  

# Change into the cloned repository
WORKDIR /app/src


ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

# Make port 7860 available to the world outside this container
EXPOSE 7860

# Run web_ui.py when the container launches
CMD ["python", "web_ui.py"]
