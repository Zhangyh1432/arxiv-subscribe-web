

import os
import sys
import requests
from dotenv import load_dotenv

# Add the parent directory to the sys.path to allow imports from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import analyzer

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# URL of the paper to be tested (e.g., a moderately sized recent paper)
# Title: "Long-Context Language Modeling with Parallel Context Encoding"
ARXIV_PAPER_URL = "https://arxiv.org/pdf/2407.16702"
LOCAL_PDF_FILENAME = "test_paper.pdf"

# Get PDF parser URL from environment variables
PDF_PARSER_URL = os.getenv("PDF_PARSER_URL")

def analyze_full_paper(markdown_content: str):
    """
    Analyzes the full markdown content of a paper using the project's analyzer.
    """
    if not analyzer.client:
        return "[Analysis Skipped: API client not initialized]"

    print("\n--- Starting Full Paper Analysis ---")
    print(f"Markdown content length: {len(markdown_content)} characters")

    try:
        # Use the same prompt template as the main application
        prompt_template_path = os.path.join(os.path.dirname(__file__), 'prompts', 'analyzer_prompt.txt')
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # We no longer have a separate title/abstract, so we adapt the prompt.
        # We'll insert the full markdown where the abstract was expected.
        prompt = prompt_template.format(title="Full Paper Analysis", abstract=markdown_content)

        messages = [{"role": "user", "content": prompt}]
        
        print("Sending request to LLM API... (This may take a while)")
        
        completion = analyzer.client.chat.completions.create(
            model="qwen-plus",
            messages=messages
        )
        return completion.choices[0].message.content

    except Exception as e:
        print(f"\n---!!! An error occurred during LLM API call !!!---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        print("This might be due to the input context exceeding the model's maximum length.")
        return f"[Analysis Failed]"

def main():
    """Main function to run the test.
    """
    if not PDF_PARSER_URL:
        print("Error: PDF_PARSER_URL not set in .env file.")
        return

    # 1. Download the PDF
    try:
        print(f"Downloading PDF from {ARXIV_PAPER_URL}...")
        response = requests.get(ARXIV_PAPER_URL)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(LOCAL_PDF_FILENAME, 'wb') as f:
            f.write(response.content)
        print(f"Successfully saved PDF as {LOCAL_PDF_FILENAME}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return

    # 2. Call the PDF parsing service
    markdown_content = ""
    try:
        print(f"\nSending PDF to parser service at {PDF_PARSER_URL}...")
        with open(LOCAL_PDF_FILENAME, 'rb') as f:
            files = {'files': (LOCAL_PDF_FILENAME, f, 'application/pdf')}
            data = {'return_md': 'true'}
            response = requests.post(PDF_PARSER_URL, files=files, data=data)
            response.raise_for_status()
            
            # The service returns a nested JSON, e.g., {"results": {"filename": {"md_content": "..."}}}
            json_response = response.json()
            if 'results' in json_response and json_response['results']:
                # Get the first result, regardless of the filename key
                first_file_key = next(iter(json_response['results']))
                if 'md_content' in json_response['results'][first_file_key]:
                    markdown_content = json_response['results'][first_file_key]['md_content']
                    print("Successfully received markdown content from parser.")
                else:
                    print("Error: 'md_content' key not found within the first result in the parser response.")
                    print("Full response:", response.text)
                    return
            else:
                print("Error: 'results' key not found or is empty in parser response.")
                print("Full response:", response.text)
                return

    except requests.exceptions.RequestException as e:
        print(f"Error calling PDF parser service: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}")
        return
    finally:
        # 3. Clean up the downloaded PDF
        if os.path.exists(LOCAL_PDF_FILENAME):
            os.remove(LOCAL_PDF_FILENAME)
            print(f"\nCleaned up {LOCAL_PDF_FILENAME}.")

    if not markdown_content:
        print("Stopping test because markdown content is empty.")
        return

    # 4. Run the analysis
    final_analysis = analyze_full_paper(markdown_content)

    print("\n--- Final Analysis Result ---")
    print(final_analysis)
    print("\n--- Test Finished ---")

if __name__ == '__main__':
    main()

