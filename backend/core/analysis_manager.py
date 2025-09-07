import os
import re
import json
import base64
import requests
import logging
from core.history_manager import load_processed_papers
from core import analyzer

# --- Constants ---
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BACKEND_DIR, '..', 'data', 'analysis_results')

def get_full_text_analysis(paper, task_status, logger):
    """
    New workflow: 
    1. Gets markdown and images from miner-u.
    2. Saves images to disk.
    3. Instructs LLM to analyze text and place image tags in its response.
    4. Rewrites relative image paths in the LLM response to absolute URLs.
    """
    processed_papers = load_processed_papers()
    paper_id = paper.get('entry_id')
    entry_id_short = paper_id.split('/')[-1]
    
    paper_result_dir = os.path.join(RESULTS_DIR, entry_id_short)
    cached_analysis_path = os.path.join(paper_result_dir, 'analysis.md')

    if paper_id in processed_papers.keys() and os.path.exists(cached_analysis_path):
        logger.info(f"Cache hit for paper {paper_id}.")
        with open(cached_analysis_path, 'r', encoding='utf-8') as f:
            return f.read()

    logger.info(f"Cache miss for paper {paper_id}. Starting full analysis.")
    os.makedirs(paper_result_dir, exist_ok=True)

    pdf_parser_url = os.getenv("PDF_PARSER_URL")
    if not pdf_parser_url:
        return "[Analysis Failed: PDF_PARSER_URL not configured]"

    pdf_url = paper.get('pdf_url')
    if not pdf_url:
        return "[Analysis Failed: Paper has no PDF URL]"

    local_pdf_filename = os.path.join(BACKEND_DIR, '..', f"{entry_id_short}.pdf")
    
    try:
        task_status['message'] = f"Downloading PDF: {paper.get('title', '')[:30]}..."
        response = requests.get(pdf_url)
        response.raise_for_status()
        with open(local_pdf_filename, 'wb') as f:
            f.write(response.content)

        task_status['message'] = f"Parsing PDF with image extraction..."
        with open(local_pdf_filename, 'rb') as f:
            files = {'files': (os.path.basename(local_pdf_filename), f, 'application/pdf')}
            data = {'return_md': 'true', 'return_images': 'true'}
            response = requests.post(pdf_parser_url, files=files, data=data)
            response.raise_for_status()
        
        json_response = response.json()
        paper_result_key = next(iter(json_response.get('results', {})), None)
        paper_result = json_response.get('results', {}).get(paper_result_key, {})

        markdown_content = paper_result.get('md_content', '')
        images_dict = paper_result.get('images', {})

        if not markdown_content:
            return "[Analysis Failed: Markdown content was empty after parsing]"
        
        raw_content_path = os.path.join(paper_result_dir, 'raw_content.md')
        with open(raw_content_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logger.info(f"Saved raw parsed content to {raw_content_path}")

        # Save images to disk so they can be served by the API
        extracted_image_filenames = []
        if images_dict:
            images_dir = os.path.join(paper_result_dir, 'images')
            os.makedirs(images_dir, exist_ok=True)
            for filename, data_uri in images_dict.items():
                try:
                    header, encoded = data_uri.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                    with open(os.path.join(images_dir, filename), 'wb') as img_f:
                        img_f.write(image_bytes)
                    extracted_image_filenames.append(filename)
                except Exception as img_e:
                    logger.error(f"Could not save image {filename}: {img_e}")

        task_status['message'] = f"Analyzing full text with LLM..."
        # The markdown_content passed to the LLM now contains the relative image paths.
        analysis_text = analyzer.analyze_full_text(markdown_content)
        
        # Rewrite relative image paths in the LLM's response to absolute URLs
        backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:5001")
        def replace_path(match):
            filename = match.group(1)
            return f"![]({backend_url}/api/images/{entry_id_short}/{filename})"

        # The regex looks for ![](images/some_image.jpg)
        rewritten_analysis_text = re.sub(r"\!\[\]\(images/(.*?)\)", replace_path, analysis_text)

        # Construct the final document
        doc_lines = [
            f"# {paper['title']}",
            f"**Authors:** {', '.join(paper['authors'])}",
            f"**Link:** {paper['pdf_url']}",
            f"**Published:** {paper['published']}",
            f"**Categories:** {', '.join(paper['categories'])}",
            rewritten_analysis_text
        ]
        full_content = "\n\n".join(doc_lines)

        # Add a figures gallery at the end of the document
        if extracted_image_filenames:
            # Prepare image URLs for the frontend
            gallery_images_data = []
            for filename in extracted_image_filenames:
                image_url = f"{backend_url}/api/images/{entry_id_short}/{filename}"
                gallery_images_data.append({"src": image_url, "alt": filename}) # Include alt text

            # Embed the image data as a JSON string within an HTML comment
            # Frontend will parse this comment to render the collapsible gallery
            gallery_json = json.dumps(gallery_images_data, ensure_ascii=False)
            full_content += f"\n\n<!-- FIGURES_GALLERY_DATA: {gallery_json} -->"
        
        # Pass extracted_image_filenames to process_paper_for_email
        return process_paper_for_email(paper, task_status, logger, full_content, extracted_image_filenames)

    except Exception as e:
        logger.error(f"Exception in analysis pipeline for {paper.get('title')}:", exc_info=e)
        return f"[Analysis Failed due to an error: {e}]"
    finally:
        if os.path.exists(local_pdf_filename):
            os.remove(local_pdf_filename)

# Modify process_paper_for_email signature
def process_paper_for_email(paper, task_status, logger, full_content, extracted_image_filenames):
    
    entry_id_short = paper['entry_id'].split('/')[-1]
    paper_result_dir = os.path.join(RESULTS_DIR, entry_id_short)
    analysis_save_path = os.path.join(paper_result_dir, 'analysis.md')
    metadata_save_path = os.path.join(paper_result_dir, 'metadata.json')

    logger.info(f"Attempting to save analysis to: {analysis_save_path}")
    try:
        os.makedirs(paper_result_dir, exist_ok=True)
        
        with open(analysis_save_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        logger.info(f"Successfully saved analysis to {analysis_save_path}")

        paper_metadata = paper.copy()
        paper_metadata['extracted_image_filenames'] = extracted_image_filenames
        with open(metadata_save_path, 'w', encoding='utf-8') as f:
            json.dump(paper_metadata, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully saved metadata to {metadata_save_path}")

    except Exception as e:
        logger.error(f"Failed to save analysis files in {paper_result_dir} due to an exception.", exc_info=True)

    sanitized_title = re.sub(r'[\/*?:"<>|]',"", paper['title'])
    email_filename = f"{sanitized_title}.md"

    return {
        'filename': email_filename,
        'content': full_content
    }