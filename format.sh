#!/bin/bash

# Specify the directory to lint, use "." to lint the entire project
# You can also specify specific files or subdirectories
TARGET_DIRECTORY="."

# Check if Ruff is installed
if ! command -v ruff &> /dev/null
then
    echo "Ruff could not be found, installing..."
    pip install ruff
fi

# Run Ruff to lint the code
echo "Running Ruff on ${TARGET_DIRECTORY}..."
ruff $TARGET_DIRECTORY

echo "Linting complete."
