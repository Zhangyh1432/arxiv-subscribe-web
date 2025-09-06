import os
import re
import requests
import logging
from core.history_manager import load_processed_ids
from core import analyzer

# --- Constants ---
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BACKEND_DIR, '..', 'data', 'analysis_results')

def get_full_text_analysis(paper, task_status, logger):
    """
    Downloads a paper's PDF, sends it to a parsing service,
    and returns the full text analysis from an LLM.
    Implements a caching mechanism to avoid re-analyzing processed papers.
    """
    processed_ids = load_processed_ids()
    paper_id = paper.get('entry_id')
    sanitized_title = re.sub(r'[\/*?:"<>|]',"", paper.get('title', ''))
    filename = f"{sanitized_title}.md"
    cached_path = os.path.join(RESULTS_DIR, filename)

    # 1. Check for cached result first
    if paper_id in processed_ids and os.path.exists(cached_path):
        logger.info(f"Cache hit for paper {paper_id}. Reading from {cached_path}.")
        try:
            with open(cached_path, 'r', encoding='utf-8') as f:
                # We need to extract just the analysis part, not the full markdown header
                full_content = f.read()
                analysis_content = full_content.split("## AI-Generated Analysis (Full Text)")[1]
                return analysis_content.strip()
        except Exception as e:
            logger.error(f"Could not read cached file {cached_path}, re-analyzing. Error: {e}")
            # Proceed to re-analysis if cache read fails

    # 2. If not cached, perform full analysis
    logger.info(f"Cache miss for paper {paper_id}. Starting full analysis.")
    pdf_parser_url = os.getenv("PDF_PARSER_URL")
    if not pdf_parser_url:
        logger.error("PDF_PARSER_URL not configured in .env file.")
        return "[Analysis Failed: PDF_PARSER_URL not configured]"

    pdf_url = paper.get('pdf_url')
    if not pdf_url:
        logger.error(f"Paper {paper.get('title')} has no PDF URL.")
        return "[Analysis Failed: Paper has no PDF URL]"

    entry_id_short = paper_id.split('/')[-1]
    local_pdf_filename = os.path.join(BACKEND_DIR, '..', f"{entry_id_short}.pdf")
    
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
        logger.error(f"Exception in analysis pipeline for {paper.get('title')}:", exc_info=e)
        return f"[Analysis Failed due to an error: {e}]"
    finally:
        if os.path.exists(local_pdf_filename):
            os.remove(local_pdf_filename)

def process_paper_for_email(paper, task_status, logger):
    analysis_text = get_full_text_analysis(paper, task_status, logger)
    
    doc_lines = []
    doc_lines.append(f"# {paper['title']}")
    doc_lines.append(f"**Authors:** {', '.join(paper['authors'])}")
    doc_lines.append(f"**Link:** {paper['pdf_url']}")
    doc_lines.append(f"**Published:** {paper['published']}")
    doc_lines.append(f"**Categories:** {', '.join(paper['categories'])}")
    doc_lines.append("\n---\n")
    doc_lines.append("## AI-Generated Analysis (Full Text)")
    doc_lines.append(analysis_text)
    
    sanitized_title = re.sub(r'[\/*?:"><>|]',"", paper['title'])
    filename = f"{sanitized_title}.md"
    content = "\n".join(doc_lines)

    # Save the analysis file locally using an absolute path
    save_path = os.path.join(RESULTS_DIR, filename)
    logger.info(f"Attempting to save analysis to absolute path: {save_path}")
    try:
        os.makedirs(RESULTS_DIR, exist_ok=True) # Ensure directory exists
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Successfully saved analysis to {save_path}")
        # Verify file existence immediately after writing
        if os.path.exists(save_path):
            logger.info(f"Verification successful: File {save_path} exists.")
        else:
            logger.error(f"Verification FAILED: File {save_path} does not exist after writing.")
    except Exception as e:
        logger.error(f"Failed to save analysis file {save_path} due to an exception.", exc_info=True)

    return {
        'filename': filename,
        'content': content
    }