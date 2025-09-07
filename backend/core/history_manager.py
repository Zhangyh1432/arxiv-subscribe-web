import os
import json

# The processed papers file is now a JSON file to store metadata.
PROCESSED_PAPERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_papers.json')

def load_processed_papers():
    """Loads the dictionary of processed papers from the JSON archive file."""
    if not os.path.exists(PROCESSED_PAPERS_FILE):
        return {}
    try:
        with open(PROCESSED_PAPERS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # If file is empty or corrupt, return an empty dictionary
        return {}

def save_processed_papers(papers):
    """Adds new papers to the JSON archive, ensuring uniqueness by entry_id."""
    if not isinstance(papers, list):
        papers = [papers]

    # Load the existing database of papers
    processed_papers_db = load_processed_papers()
    
    new_papers_added = 0
    for paper in papers:
        if not isinstance(paper, dict):
            # This case should ideally not happen with the new flow
            continue 

        entry_id = paper.get('entry_id')
        if not entry_id:
            continue

        # Add or update the paper in the database, ensuring no duplicates
        if entry_id not in processed_papers_db:
            processed_papers_db[entry_id] = paper
            new_papers_added += 1

    if new_papers_added == 0:
        print("No new papers to save to the processed papers database.")
        return

    # Write the entire updated database back to the JSON file
    try:
        with open(PROCESSED_PAPERS_FILE, "w", encoding='utf-8') as f:
            json.dump(processed_papers_db, f, ensure_ascii=False, indent=4)
        print(f"Saved {new_papers_added} new papers to the processed papers database.")
    except IOError as e:
        print(f"Error saving processed papers database: {e}")