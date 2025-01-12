#!/bin/bash

echo "Pulling latest changes..."
git pull

echo "Rebuilding and restarting containers..."
docker compose down
docker compose up --build -d

echo "Update complete!"
