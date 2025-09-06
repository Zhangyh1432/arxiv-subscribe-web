import re
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
load_dotenv()

# Initialize the OpenAI client for translation
# This should be done once, so we do it at the module level.
try:
    # Check for the API key *after* loading .env
    api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("Warning: DASHSCOPE_API_KEY environment variable not set. Translation will be skipped.")
        TRANSLATION_ENABLED = False
        client = None
    else:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        TRANSLATION_ENABLED = True
except Exception as e:
    print(f"Error initializing OpenAI client for translation: {e}")
    TRANSLATION_ENABLED = False
    client = None


def _translate_text(text, target_lang="Chinese"):
    """Translates text using the DashScope API with a specific domain style."""
    if not TRANSLATION_ENABLED or not text or not client:
        return "[Translation Skipped]"

    try:
        messages = [{"role": "user", "content": text}]
        translation_options = {
            "source_lang": "auto",
            "target_lang": target_lang,
            "domains": "Translate to Chinese for academic papers in the field of Computer Science. Use precise and formal technical language."
        }
        
        completion = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=messages,
            extra_body={"translation_options": translation_options}
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during translation: {e}")
        return f"[Translation Failed: {text[:30]}...]"

def generate_markdown_files_content(papers_by_category):
    """
    Generates content for one Markdown file per category, including translations.
    Returns a list of dictionaries, each with 'filename' and 'content'.
    """
    files = []
    if not papers_by_category:
        return files

    print("Translating titles and abstracts... (This may take a while)")
    for category, papers in papers_by_category.items():
        if not papers:
            continue

        sanitized_category = re.sub(r'[\\/*?:"<>|]', "_", category)
        filename = f"{sanitized_category}.md"
        
        category_doc_lines = [f"# Papers for Category: {category}\n"]
        
        for paper in papers:
            translated_title = _translate_text(paper.title, target_lang="Chinese")
            # The abstract can be long, so we translate sentence by sentence might be better, but for now, let's do it at once.
            translated_summary = _translate_text(paper.summary.replace('\n', ' '), target_lang="Chinese")

            category_doc_lines.append(f"## {paper.title}")
            category_doc_lines.append(f"**翻译标题:** {translated_title}\n")
            
            authors = ", ".join([author.name for author in paper.authors])
            category_doc_lines.append(f"**Authors:** {authors}")
            category_doc_lines.append(f"**Link:** [{paper.pdf_url}]({paper.pdf_url})\n")
            
            category_doc_lines.append("**Abstract:**")
            category_doc_lines.append(f"> {paper.summary}")
            category_doc_lines.append(f"**翻译摘要:**\n> {translated_summary}\n")
            
            category_doc_lines.append("\n---\n")

        files.append({
            'filename': filename,
            'content': "\n".join(category_doc_lines)
        })
    print("Translation finished.")
    return files

# ... (The if __name__ == '__main__': block can remain for testing, but it won't test the translation)