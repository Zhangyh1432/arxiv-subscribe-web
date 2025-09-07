from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS, cross_origin
import threading
import os
import requests
import logging
import shutil
import json
from core import arxiv_fetcher, analyzer, email_sender
from core.history_manager import save_processed_papers, PROCESSED_PAPERS_FILE
from core.analysis_manager import process_paper_for_email, RESULTS_DIR, get_full_text_analysis
import re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

logging.basicConfig(level=logging.INFO)

# --- Global Status and Cache Objects ---
task_status = {"status": "idle", "message": "The service is idle."}
results_cache = []

# --- Helper: Analysis Task Runner ---
def run_analysis_for_paper(paper):
    dummy_task_status = {'message': ''} 
    get_full_text_analysis(paper, dummy_task_status, app.logger)
    save_processed_papers([paper])
    app.logger.info(f"Background analysis finished for {paper.get('entry_id')}")

# --- API Endpoints ---

@app.route('/api/run-fetch', methods=['POST'])
def run_fetch():
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
    file_path = os.path.join(RESULTS_DIR, paper_id, 'analysis.md')
    metadata_path = os.path.join(RESULTS_DIR, paper_id, 'metadata.json') # <-- 添加这一行
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            extracted_image_filenames = []
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f_meta:
                    metadata = json.load(f_meta)
                    extracted_image_filenames = metadata.get('extracted_image_filenames', [])

            return jsonify({"status": "success", "content": content, "extracted_image_filenames": extracted_image_filenames})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "running"})

@app.route('/api/images/<path:paper_id>/<path:filename>')
def serve_image(paper_id, filename):
    """Serves an extracted image from the analysis results directory."""
    image_directory = os.path.join(RESULTS_DIR, paper_id, 'images')
    return send_from_directory(image_directory, filename)

@app.route('/api/email-result', methods=['POST'])
def email_result():
    data = request.json
    paper = data.get('paper')
    recipient_email = data.get('email')
    if not paper or not recipient_email:
        return jsonify({"error": "Paper data and recipient email are required."}), 400
    entry_id_short = paper['entry_id'].split('/')[-1]
    file_path = os.path.join(RESULTS_DIR, entry_id_short, 'analysis.md')
    if not os.path.exists(file_path):
        return jsonify({"error": "Analysis result not found."}), 404
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        sanitized_title = re.sub(r'[\\/*?:"<>|]',"", paper['title'])
        email_filename = f"{sanitized_title}.md"
        file_to_send = {'filename': email_filename, 'content': content}
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
    global task_status
    try:
        files_to_zip = []
        total_papers = len(selected_papers)
        
        for i, paper in enumerate(selected_papers):
            task_status['message'] = f"Processing paper {i+1}/{total_papers}: {paper['title'][:40]}..."
            files_to_zip.append(process_paper_for_email(paper, task_status, app.logger))

        task_status['message'] = "Zipping and sending email..."
        subject = f"Bulk Analysis Results for {total_papers} Papers"
        email_sent = email_sender.send_email(files_to_zip, total_papers, recipient_email, subject)

        if email_sent:
            save_processed_papers(selected_papers)
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
    global task_status
    if task_status.get('status') == 'running':
        return jsonify({"message": "A bulk analysis task is already in progress."}), 409

    data = request.json
    selected_papers = data.get('papers', [])
    recipient_email = data.get('email', None)

    if not selected_papers:
        return jsonify({"message": "No papers selected for analysis."}), 400

    task_status = {'status': 'running', 'message': 'Bulk analysis task started...'}
    thread = threading.Thread(target=analysis_task_wrapper, args=(selected_papers, recipient_email))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Bulk analysis process started successfully."}), 202

# --- Other Endpoints ---

def fetch_task_wrapper(date_range=None, categories=None, keywords=None):
    global task_status, results_cache
    try:
        papers_by_category = arxiv_fetcher.fetch_papers(date_range, categories, keywords)
        all_papers = [p for papers in papers_by_category.values() for p in papers]
        unique_papers = list({p['entry_id']: p for p in all_papers}.values())
        total_unique_papers = len(unique_papers)
        app.logger.info(f"Found {total_unique_papers} papers.")

        if total_unique_papers > 0:
            results_cache = unique_papers
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

@app.route('/api/status', methods=['GET'])
def get_status():
    global task_status
    return jsonify(task_status)

@app.route('/api/results', methods=['GET'])
def get_results():
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

# --- History/Warehouse Endpoints ---

@app.route('/api/all-analyses', methods=['GET'])
def get_all_analyses():
    query = request.args.get('query', '').lower()
    all_metadata = []
    if not os.path.exists(RESULTS_DIR):
        return jsonify([])
    for paper_id_dir in os.listdir(RESULTS_DIR):
        metadata_path = os.path.join(RESULTS_DIR, paper_id_dir, 'metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['short_id'] = paper_id_dir
                if not query or (query in metadata.get('title', '').lower()) or (query in metadata.get('entry_id', '').lower()):
                    all_metadata.append(metadata)
            except Exception as e:
                app.logger.error(f"Error reading metadata for {paper_id_dir}: {e}")
    all_metadata.sort(key=lambda x: x.get('published', ''), reverse=True)
    return jsonify(all_metadata)

@app.route('/api/recent-analyses', methods=['GET'])
def get_recent_analyses():
    all_metadata = []
    if not os.path.exists(RESULTS_DIR):
        return jsonify([])
    for paper_id_dir in os.listdir(RESULTS_DIR):
        dir_path = os.path.join(RESULTS_DIR, paper_id_dir)
        if not os.path.isdir(dir_path):
            continue
        metadata_path = os.path.join(dir_path, 'metadata.json')
        if os.path.exists(metadata_path):
            try:
                mod_time = os.path.getmtime(dir_path)
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['short_id'] = paper_id_dir
                metadata['mod_time'] = mod_time
                all_metadata.append(metadata)
            except Exception as e:
                app.logger.error(f"Error processing directory {paper_id_dir}: {e}", exc_info=True)
    all_metadata.sort(key=lambda x: x.get('mod_time', 0), reverse=True)
    return jsonify(all_metadata[:10])

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    app.logger.info("Received request to clear cache.")
    try:
        if os.path.exists(RESULTS_DIR):
            for filename in os.listdir(RESULTS_DIR):
                file_path = os.path.join(RESULTS_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    app.logger.error(f'Failed to delete {file_path}. Reason: {e}')
        
        processed_json = PROCESSED_PAPERS_FILE
        if os.path.exists(processed_json):
            os.remove(processed_json)

        app.logger.info("Cache cleared successfully.")
        return jsonify({"message": "Cache cleared successfully."}), 200
    except Exception as e:
        app.logger.error(f"Failed to clear cache. Reason: {e}")
        return jsonify({"message": "An error occurred while clearing the cache."}), 500

@app.route('/api/translate', methods=['POST'])
@cross_origin(origins="http://localhost:3000", methods=['POST'], headers=['Content-Type'])
def translate_paper_content():
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

if __name__ == '__main__':
    # Read port from environment variable, default to 5001 if not set
    port = int(os.environ.get("BACKEND_PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)