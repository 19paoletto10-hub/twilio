FROM mcr.microsoft.com/devcontainers/python:0-3.12

# Create app directory and set permissions for the vscode user
WORKDIR /workspaces/twilio

COPY . /workspaces/twilio

USER root
RUN pip install --upgrade pip && pip install --no-cache-dir -r /workspaces/twilio/requirements.txt || true

USER vscode
