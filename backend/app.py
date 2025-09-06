from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import threading
import os
import requests
import logging
from core import arxiv_fetcher, analyzer, email_sender
from core.history_manager import save_processed_ids
from core.analysis_manager import process_paper_for_email, RESULTS_DIR
import re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Status and Cache Objects ---
task_status = {"status": "idle", "message": "The service is idle."}
results_cache = []

# --- Helper: Analysis Task Runner ---
def run_analysis_for_paper(paper):
    """The actual analysis process for a single paper, designed to be run in a thread."""
    dummy_task_status = {'message': ''} 
    process_paper_for_email(paper, dummy_task_status, app.logger)
    save_processed_ids([paper])
    app.logger.info(f"Background analysis finished for {paper.get('entry_id')}")

# --- API Endpoints ---

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

# --- Single Paper Analysis Workflow ---

@app.route('/api/analyze-paper', methods=['POST'])
def analyze_paper():
    """Triggers the analysis for a single paper in the background."""
    paper = request.json.get('paper')
    if not paper:
        return jsonify({"error": "Paper data is required."}), 400
    
    thread = threading.Thread(target=run_analysis_for_paper, args=(paper,))
    thread.daemon = True
    thread.start()
    
    app.logger.info(f"Started background analysis for {paper.get('entry_id')}")
    return jsonify({"message": "Analysis has been started."}), 202

@app.route('/api/analysis-status/<path:paper_id>', methods=['GET'])
def get_analysis_status(paper_id):
    """
    Checks if an analysis result file exists. If so, returns the content.
    If not, returns a 'running' status.
    """
    title = request.args.get('title')
    if not title:
        return jsonify({"status": "error", "message": "Title parameter is required."}), 400

    sanitized_title = re.sub(r'[\\/*?:"<>|]',"", title)
    filename = f"{sanitized_title}.md"
    file_path = os.path.join(RESULTS_DIR, filename)

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"status": "success", "content": content})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "running"})

@app.route('/api/email-result', methods=['POST'])
def email_result():
    """Emails an already generated analysis result."""
    data = request.json
    paper = data.get('paper')
    recipient_email = data.get('email')

    if not paper or not recipient_email:
        return jsonify({"error": "Paper data and recipient email are required."}), 400

    sanitized_title = re.sub(r'[\\/*?:"<>|]',"", paper['title'])
    filename = f"{sanitized_title}.md"
    file_path = os.path.join(RESULTS_DIR, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "Analysis result not found. Please analyze the paper first."}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_to_send = {'filename': filename, 'content': content}
        subject = paper.get('title', 'Single Paper Analysis')

        email_sent = email_sender.send_email([file_to_send], 1, recipient_email, subject)

        if email_sent:
            return jsonify({"message": "Email sent successfully."})
        else:
            return jsonify({"error": "Failed to send email."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Bulk Analysis Workflow ---

def analysis_task_wrapper(selected_papers, recipient_email=None):
    """
    Wrapper for the bulk analysis and emailing task, using the new analysis manager.
    """
    global task_status
    try:
        files_to_zip = []
        total_papers = len(selected_papers)
        
        for i, paper in enumerate(selected_papers):
            # This now uses the caching mechanism implicitly
            files_to_zip.append(process_paper_for_email(paper, task_status, app.logger))

        subject = f"Bulk Analysis Results for {total_papers} Papers"
        task_status['message'] = f"All {total_papers} papers processed. Zipping and sending email..."
        email_sent = email_sender.send_email(files_to_zip, total_papers, recipient_email, subject)

        if email_sent:
            save_processed_ids(selected_papers)
            task_status['status'] = 'success'
            task_status['message'] = f"Process complete. Emailed {total_papers} analyzed papers."
        else:
            task_status['status'] = 'error'
            task_status['message'] = "Email sending failed during bulk analysis stage."

    except Exception as e:
        task_status['status'] = 'error'
        task_status['message'] = str(e)
        app.logger.error("Exception in analysis_task_wrapper:", exc_info=e)
    finally:
        app.logger.info(f"Bulk analysis task finished with status: {task_status['status']}")

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
    task_status['message'] = 'Bulk analysis task started...'
    
    thread = threading.Thread(target=analysis_task_wrapper, args=(selected_papers, recipient_email))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Bulk analysis process started successfully."}), 202

# --- Other Endpoints ---

def fetch_task_wrapper(date_range=None, categories=None, keywords=None):
    """A wrapper to run the fetch logic and update the status."""
    global task_status, results_cache
    try:
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
