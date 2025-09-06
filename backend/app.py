from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import threading
import os
import requests
import logging
from core import arxiv_fetcher, analyzer, email_sender
from core.history_manager import load_processed_ids, save_processed_ids
import re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Constants ---
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BACKEND_DIR, 'data', 'analysis_results')

# --- Status and Cache Objects ---
task_status = {"status": "idle", "message": "The service is idle."}
results_cache = []

# --- Full Analysis Helper Function ---
def _get_full_text_analysis(paper):
    """
    Downloads a paper's PDF, sends it to a parsing service,
    and returns the full text analysis from an LLM.
    Implements a caching mechanism to avoid re-analyzing processed papers.
    """
    processed_ids = load_processed_ids()
    paper_id = paper.get('entry_id')
    sanitized_title = re.sub(r'[\\/*?:"<>|]',"", paper.get('title', ''))
    filename = f"{sanitized_title}.md"
    cached_path = os.path.join(RESULTS_DIR, filename)

    # 1. Check for cached result first
    if paper_id in processed_ids and os.path.exists(cached_path):
        app.logger.info(f"Cache hit for paper {paper_id}. Reading from {cached_path}.")
        try:
            with open(cached_path, 'r', encoding='utf-8') as f:
                # We need to extract just the analysis part, not the full markdown header
                full_content = f.read()
                analysis_content = full_content.split("## AI-Generated Analysis (Full Text)")[1]
                return analysis_content.strip()
        except Exception as e:
            app.logger.error(f"Could not read cached file {cached_path}, re-analyzing. Error: {e}")
            # Proceed to re-analysis if cache read fails

    # 2. If not cached, perform full analysis
    app.logger.info(f"Cache miss for paper {paper_id}. Starting full analysis.")
    pdf_parser_url = os.getenv("PDF_PARSER_URL")
    if not pdf_parser_url:
        app.logger.error("PDF_PARSER_URL not configured in .env file.")
        return "[Analysis Failed: PDF_PARSER_URL not configured]"

    pdf_url = paper.get('pdf_url')
    if not pdf_url:
        app.logger.error(f"Paper {paper.get('title')} has no PDF URL.")
        return "[Analysis Failed: Paper has no PDF URL]"

    entry_id_short = paper_id.split('/')[-1]
    local_pdf_filename = os.path.join(BACKEND_DIR, f"{entry_id_short}.pdf")
    
    try:
        task_status['message'] = f"Downloading PDF: {paper.get('title', '')[:30]}..."
        response = requests.get(pdf_url)
        response.raise_for_status()
        with open(local_pdf_filename, 'wb') as f:
            f.write(response.content)

        task_status['message'] = f"Parsing PDF: {paper.get('title', '')[:30]}..."
        with open(local_pdf_filename, 'rb') as f:
            files = {'files': (os.path.basename(local_pdf_filename), f, 'application/pdf')}
            data = {'return_md': 'true'}
            response = requests.post(pdf_parser_url, files=files, data=data)
            response.raise_for_status()
        
        json_response = response.json()
        markdown_content = json_response['results'][next(iter(json_response['results']))]['md_content']

        if not markdown_content:
            return "[Analysis Failed: Markdown content was empty after parsing]"
        
        task_status['message'] = f"Analyzing full text: {paper.get('title', '')[:30]}..."
        analysis_text = analyzer.analyze_full_text(markdown_content)
        return analysis_text

    except Exception as e:
        app.logger.error(f"Exception in analysis pipeline for {paper.get('title')}:", exc_info=e)
        return f"[Analysis Failed due to an error: {e}]"
    finally:
        if os.path.exists(local_pdf_filename):
            os.remove(local_pdf_filename)

# --- Helper function for paper processing ---
def _process_paper_for_email(paper):
    analysis_text = _get_full_text_analysis(paper)
    
    doc_lines = []
    doc_lines.append(f"# {paper['title']}")
    doc_lines.append(f"**Authors:** {', '.join(paper['authors'])}")
    doc_lines.append(f"**Link:** {paper['pdf_url']}")
    doc_lines.append(f"**Published:** {paper['published']}")
    doc_lines.append(f"**Categories:** {', '.join(paper['categories'])}")
    doc_lines.append("\n---\n")
    doc_lines.append("## AI-Generated Analysis (Full Text)")
    doc_lines.append(analysis_text)
    
    sanitized_title = re.sub(r'[\\/*?:"<>|]',"", paper['title'])
    filename = f"{sanitized_title}.md"
    content = "\n".join(doc_lines)

    # Save the analysis file locally using an absolute path
    save_path = os.path.join(RESULTS_DIR, filename)
    try:
        os.makedirs(RESULTS_DIR, exist_ok=True) # Ensure directory exists
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        app.logger.info(f"Successfully saved analysis to {save_path}")
    except Exception as e:
        app.logger.error(f"Failed to save analysis file {save_path}: {e}")

    return {
        'filename': filename,
        'content': content
    }

# --- Fetching Logic ---
def fetch_task_wrapper(date_range=None, categories=None, keywords=None):
    """A wrapper to run the fetch logic and update the status."""
    global task_status, results_cache
    try:
        # User wants to see all papers, not filter them, so we don't check history here.
        papers_by_category = arxiv_fetcher.fetch_papers(date_range, categories, keywords)
        
        all_papers_dict = {p['entry_id']: p for papers in papers_by_category.values() for p in papers}
        
        total_unique_papers = len(all_papers_dict)
        app.logger.info(f"Found {total_unique_papers} papers.")

        if total_unique_papers > 0:
            results_cache = list(all_papers_dict.values())
            task_status['status'] = 'review_ready'
            task_status['message'] = f"Found {total_unique_papers} papers. Ready for review."
        else:
            task_status['status'] = 'success'
            task_status['message'] = "Process finished. No new papers found."
    except Exception as e:
        task_status['status'] = 'error'
        task_status['message'] = str(e)
        app.logger.error("Exception in fetch_task_wrapper:", exc_info=e)
    finally:
        app.logger.info(f"Fetch task finished with status: {task_status['status']}")

@app.route('/api/run-fetch', methods=['POST'])
def run_fetch():
    """Starts the fetching process based on criteria from the frontend."""
    global task_status, results_cache
    if task_status['status'] == 'running':
        return jsonify({"message": "A task is already in progress."}), 409

    results_cache = []
    data = request.json if request.json else {}
    
    task_status['status'] = 'running'
    task_status['message'] = 'Fetching papers...'
    
    thread = threading.Thread(target=fetch_task_wrapper, kwargs=data)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Fetch process started successfully."}), 202

# --- Analysis and Emailing Logic (Bulk) ---
def analysis_task_wrapper(selected_papers, recipient_email=None):
    """
    Wrapper for the bulk analysis and emailing task.
    """
    global task_status
    try:
        files_to_zip = []
        total_papers = len(selected_papers)
        
        for i, paper in enumerate(selected_papers):
            files_to_zip.append(_process_paper_for_email(paper))

        subject = None
        if total_papers == 1:
            subject = selected_papers[0].get('title', 'Single Paper Analysis')

        task_status['message'] = f"All {total_papers} papers analyzed. Zipping and sending email..."
        email_sent = email_sender.send_email(files_to_zip, total_papers, recipient_email, subject)

        if email_sent:
            save_processed_ids(selected_papers)
            task_status['status'] = 'success'
            task_status['message'] = f"Process complete. Emailed {total_papers} analyzed papers."
        else:
            task_status['status'] = 'error'
            task_status['message'] = "Email sending failed during analysis stage."

    except Exception as e:
        task_status['status'] = 'error'
        task_status['message'] = str(e)
        app.logger.error("Exception in analysis_task_wrapper:", exc_info=e)
    finally:
        app.logger.info(f"Bulk analysis task finished with status: {task_status['status']}")

@app.route('/api/translate', methods=['POST'])
@cross_origin(origins="http://localhost:3000", methods=['POST'], headers=['Content-Type'])
def translate_paper_content():
    """Translates the title and abstract of a paper."""
    data = request.json
    title = data.get('title')
    abstract = data.get('abstract')

    if not title or not abstract:
        return jsonify({"error": "Title and abstract are required."}), 400

    try:
        combined_text = f"Title: {title}\n\nAbstract: {abstract}"
        translated_combined = analyzer.translate_text(combined_text)
        
        translated_title = ""
        translated_abstract = ""
        
        title_prefixes = r"^(Translated: )?Title:?\s*"
        abstract_prefixes = r"^(Translated: )?Abstract:?\s*"

        title_match = re.search(r"Title:(.*?)(?:\n\nAbstract:|$)", translated_combined, re.DOTALL | re.IGNORECASE)
        abstract_match = re.search(r"Abstract:(.*)", translated_combined, re.DOTALL | re.IGNORECASE)

        if title_match:
            translated_title = re.sub(title_prefixes, "", title_match.group(1).strip(), flags=re.IGNORECASE)
        
        if abstract_match:
            translated_abstract = re.sub(abstract_prefixes, "", abstract_match.group(1).strip(), flags=re.IGNORECASE)

        if not translated_title and not translated_abstract:
            translated_abstract = translated_combined.strip()
            first_line = translated_combined.split('\n', 1)[0].strip()
            if len(first_line) < 100 and not first_line.lower().startswith(('abstract', 'summary')):
                translated_title = re.sub(title_prefixes, "", first_line, flags=re.IGNORECASE)
                if translated_title:
                    translated_abstract = translated_combined.replace(first_line, '', 1).strip()
                else:
                    translated_abstract = translated_combined.strip()

        translated_title = re.sub(title_prefixes, "", translated_title, flags=re.IGNORECASE).strip()
        translated_abstract = re.sub(abstract_prefixes, "", translated_abstract, flags=re.IGNORECASE).strip()

        if not translated_title and not translated_abstract:
            translated_title = "(Translation Error)"
            translated_abstract = translated_combined
        elif not translated_title:
            translated_title = "(No Title Translation)"
        elif not translated_abstract:
            translated_abstract = "(No Abstract Translation)"

        return jsonify({
            "translated_title": translated_title.strip(),
            "translated_abstract": translated_abstract.strip()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-and-email', methods=['POST'])
def analyze_and_email():
    """Starts the bulk analysis and emailing process for selected papers."""
    global task_status
    if task_status['status'] == 'running':
        return jsonify({"message": "A task is already in progress."}), 409

    data = request.json if request.json else {}
    selected_papers = data.get('papers', [])
    recipient_email = data.get('email', None)

    if not selected_papers:
        return jsonify({"message": "No papers selected for analysis."}), 400

    task_status['status'] = 'running'
    task_status['message'] = 'Analysis task started...'
    
    thread = threading.Thread(target=analysis_task_wrapper, args=(selected_papers, recipient_email))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Analysis process started successfully."}), 202

@app.route('/api/analyze-single-paper', methods=['POST'])
def analyze_single_paper():
    """
    Analyzes and emails a single paper synchronously.
    """
    data = request.json if request.json else {}
    paper = data.get('paper')
    recipient_email = data.get('email', None)

    if not paper:
        return jsonify({"message": "No paper provided for analysis."}), 400

    try:
        file_to_zip = [_process_paper_for_email(paper)]
        subject = paper.get('title', 'Single Paper Analysis')
        
        email_sent = email_sender.send_email(file_to_zip, 1, recipient_email, subject)

        if email_sent:
            save_processed_ids([paper])
            return jsonify({"message": "Paper analyzed and emailed successfully.", "status": "success"}), 200
        else:
            return jsonify({"message": "Email sending failed.", "status": "error"}), 500
    except Exception as e:
        app.logger.error("Exception in analyze_single_paper:", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

# --- Shared Endpoints ---
@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the current status of the background task."""
    global task_status
    return jsonify(task_status)

@app.route('/api/results', methods=['GET'])
def get_results():
    """Returns paginated results from the cache."""
    global results_cache
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    if not results_cache:
        return jsonify({"message": "No results available."}), 404

    start = (page - 1) * per_page
    end = start + per_page
    paginated_results = results_cache[start:end]

    response = {
        "papers": paginated_results,
        "total_papers": len(results_cache),
        "page": page,
        "per_page": per_page
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
