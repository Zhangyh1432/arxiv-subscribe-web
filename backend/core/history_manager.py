import os

PROCESSED_PAPERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_papers.txt')

def load_processed_ids():
    """Loads processed paper IDs from the archive file."""
    if not os.path.exists(PROCESSED_PAPERS_FILE):
        return set()
    with open(PROCESSED_PAPERS_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_processed_ids(papers):
    """Appends the IDs of newly processed papers to the archive file, ensuring uniqueness."""
    if not isinstance(papers, list):
        papers = [papers]

    unique_ids_to_add = set()
    for paper in papers:
        if isinstance(paper, dict):
            unique_ids_to_add.add(paper.get('entry_id'))
        else:
            unique_ids_to_add.add(paper.entry_id)
    
    unique_ids_to_add.discard(None);

    if not unique_ids_to_add:
        return

    # Load existing IDs to prevent writing duplicates
    existing_ids = load_processed_ids()
    truly_new_ids = unique_ids_to_add - existing_ids

    if not truly_new_ids:
        print("No new paper IDs to save.")
        return

    with open(PROCESSED_PAPERS_FILE, "a") as f:
        for paper_id in truly_new_ids:
            f.write(f"{paper_id}\n")
    
    print(f"Saved {len(truly_new_ids)} new unique paper IDs to archive.")
