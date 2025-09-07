import os
import re
import json
import requests
import logging
from core.history_manager import load_processed_papers
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
    processed_papers = load_processed_papers()
    paper_id = paper.get('entry_id')
    entry_id_short = paper_id.split('/')[-1]
    
    paper_result_dir = os.path.join(RESULTS_DIR, entry_id_short)
    cached_analysis_path = os.path.join(paper_result_dir, 'analysis.md')

    # 1. Check for cached result first
    if paper_id in processed_papers.keys() and os.path.exists(cached_analysis_path):
        logger.info(f"Cache hit for paper {paper_id}. Reading from {cached_analysis_path}.")
        try:
            with open(cached_analysis_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
            # The file now contains the full report, just return it.
            return full_content
        except Exception as e:
            logger.error(f"Could not read cached file {cached_analysis_path}, re-analyzing. Error: {e}")
            # Proceed to re-analysis if cache read fails

    # 2. If not cached, perform full analysis
    logger.info(f"Cache miss for paper {paper_id}. Starting full analysis.")
    os.makedirs(paper_result_dir, exist_ok=True)

    pdf_parser_url = os.getenv("PDF_PARSER_URL")
    if not pdf_parser_url:
        logger.error("PDF_PARSER_URL not configured in .env file.")
        return "[Analysis Failed: PDF_PARSER_URL not configured]"

    pdf_url = paper.get('pdf_url')
    if not pdf_url:
        logger.error(f"Paper {paper.get('title')} has no PDF URL.")
        return "[Analysis Failed: Paper has no PDF URL]"

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
        
        raw_content_path = os.path.join(paper_result_dir, 'raw_content.md')
        with open(raw_content_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logger.info(f"Saved raw parsed content to {raw_content_path}")

        task_status['message'] = f"Analyzing full text: {paper.get('title', '')[:30]}..."
        analysis_text = analyzer.analyze_full_text(markdown_content)
        
        # Construct the full document content here before returning
        doc_lines = []
        doc_lines.append(f"# {paper['title']}")
        doc_lines.append(f"**Authors:** {', '.join(paper['authors'])}")
        doc_lines.append(f"**Link:** {paper['pdf_url']}")
        doc_lines.append(f"**Published:** {paper['published']}")
        doc_lines.append(f"**Categories:** {', '.join(paper['categories'])}")
        doc_lines.append(analysis_text)
        full_content = "\n\n".join(doc_lines)
        return full_content

    except Exception as e:
        logger.error(f"Exception in analysis pipeline for {paper.get('title')}:", exc_info=e)
        return f"[Analysis Failed due to an error: {e}]"
    finally:
        if os.path.exists(local_pdf_filename):
            os.remove(local_pdf_filename)

def process_paper_for_email(paper, task_status, logger):
    # This function now gets the full content, including headers
    full_content = get_full_text_analysis(paper, task_status, logger)
    
    # Define paths for the new structure
    entry_id_short = paper['entry_id'].split('/')[-1]
    paper_result_dir = os.path.join(RESULTS_DIR, entry_id_short)
    analysis_save_path = os.path.join(paper_result_dir, 'analysis.md')
    metadata_save_path = os.path.join(paper_result_dir, 'metadata.json')

    # Save the analysis file and metadata file locally
    logger.info(f"Attempting to save analysis to: {analysis_save_path}")
    try:
        os.makedirs(paper_result_dir, exist_ok=True) # Ensure directory exists
        
        with open(analysis_save_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        logger.info(f"Successfully saved analysis to {analysis_save_path}")

        with open(metadata_save_path, 'w', encoding='utf-8') as f:
            json.dump(paper, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully saved metadata to {metadata_save_path}")

    except Exception as e:
        logger.error(f"Failed to save analysis files in {paper_result_dir} due to an exception.", exc_info=True)

    # For email attachments, a user-friendly name is better.
    sanitized_title = re.sub(r'[\/*?:"<>|]',"", paper['title'])
    email_filename = f"{sanitized_title}.md"

    return {
        'filename': email_filename,
        'content': full_content
    }