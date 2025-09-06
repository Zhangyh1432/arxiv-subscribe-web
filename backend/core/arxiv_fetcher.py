import arxiv
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re

PROCESSED_PAPERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed_papers.txt')
CATEGORIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'arxiv_categories.txt')
FETCH_LIMIT = 300

def load_all_categories():
    """Loads all categories from the data file."""
    if not os.path.exists(CATEGORIES_FILE):
        return []
    with open(CATEGORIES_FILE, "r") as f:
        content = f.read()
    return re.findall(r'\*\s+([a-zA-Z\.\-]+)', content, re.MULTILINE)


def get_date_query_from_range(date_range):
    """Calculates start and end dates and returns an arXiv query string."""
    if not date_range or date_range == "recent":
        return ""
    
    end_date = datetime.now()
    start_date = None

    if date_range == "last_month":
        start_date = end_date - relativedelta(months=1)
    elif date_range == "last_3_months":
        start_date = end_date - relativedelta(months=3)
    elif date_range == "last_year":
        start_date = end_date - relativedelta(years=1)
    elif date_range == "last_2_years":
        start_date = end_date - relativedelta(years=2)
    else:
        return "" # Invalid range

    start_str = start_date.strftime("%Y%m%d0000")
    end_str = end_date.strftime("%Y%m%d2359")
    print(f"Date Range Query: From {start_date.date()} to {end_date.date()}")
    return f" AND submittedDate:[{start_str} TO {end_str}]"

def fetch_papers(date_range=None, categories=None, keywords=None):
    """
    Fetches papers from arXiv based on a date range, categories, and keywords.
    """
    if not categories:
        print("No categories selected, defaulting to all categories.")
        search_categories = load_all_categories()
        if not search_categories:
            print("Could not load categories from file.")
            return {}
    else:
        search_categories = categories

    category_query = " OR ".join([f"cat:{cat}" for cat in search_categories])
    
    keyword_query = ""
    if keywords:
        keyword_parts = [f'ti:"{kw}" OR abs:"{kw}"' for kw in keywords]
        keyword_query = " AND (" + " OR ".join(keyword_parts) + ")"

    date_query = get_date_query_from_range(date_range)

    final_query = f"({category_query}){keyword_query}{date_query}"
    print(f"Executing arXiv API query (limit: {FETCH_LIMIT}): {final_query}")

    search = arxiv.Search(
        query=final_query,
        max_results=FETCH_LIMIT,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    client = arxiv.Client()
    all_results = {}
    try:
        results_generator = client.results(search)
        for result in results_generator:
            all_results[result.entry_id] = result
    except Exception as e:
        print(f"Error during search: {e}")

    final_papers = list(all_results.values())

    papers_by_category = {category: [] for category in search_categories}
    for paper in final_papers:
        for category in paper.categories:
            if category in papers_by_category:
                papers_by_category[category].append(paper)

    json_output = {}
    for category, papers in papers_by_category.items():
        if not papers: continue
        json_output[category] = []
        for paper in papers:
            json_output[category].append({
                "entry_id": paper.entry_id,
                "title": paper.title,
                "summary": paper.summary,
                "authors": [author.name for author in paper.authors],
                "pdf_url": paper.pdf_url,
                "published": paper.published.isoformat(),
                "categories": paper.categories
            })

    return json_output