#!/bin/bash
# This script runs the arXiv subscription project.
# It passes all command-line arguments directly to the Python script.
# Example: ./run.sh --date 2024-01-10

echo "--- Activating conda environment and running project ---"
conda run -n arxiv-subscribe python -m src.main "$@"
echo "--- Script finished ---"
