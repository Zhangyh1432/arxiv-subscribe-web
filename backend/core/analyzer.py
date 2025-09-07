import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize client in a try-except block to handle potential errors
try:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("Warning: DASHSCOPE_API_KEY not set. Analysis will be skipped.")
        client = None
    else:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None

def analyze_paper(title, abstract):
    """
    Calls an LLM to generate a detailed analysis of a paper based on its title and abstract.
    """
    if not client:
        return "[Analysis Skipped: API client not initialized]"

    print(f"Analyzing paper (abstract only): {title[:50]}...")
    
    with open(os.path.join(os.path.dirname(__file__), '..', 'prompts', 'analyzer_prompt.txt'), 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # Correctly concatenate the prompt and the paper content
    paper_content = f"Title: {title}\n\nAbstract: {abstract}"
    prompt = (
        prompt_template + 
        "\n\n---\n\n" +
        "请基于以上要求, 对以下论文摘要内容进行分析:\n\n" +
        paper_content
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during analysis for '{title[:30]}...': {e}")
        return f"[Analysis Failed]"

def translate_text(text_to_translate):
    """
    Calls the specialized Qwen-MT-Turbo model for translation.
    """
    if not client:
        return "[Translation Skipped: API client not initialized]"

    print(f"Translating text via Qwen-MT-Turbo: {text_to_translate[:50]}...")

    try:
        messages = [{
            "role": "user",
            "content": text_to_translate
        }]
        
        translation_options = {
            "source_lang": "auto",
            "target_lang": "Chinese",
            "domains": "academic paper, computer science, scientific research"
        }

        completion = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=messages,
            extra_body={
                "translation_options": translation_options
            }
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error during translation: {e}")
        return f"[Translation Failed: {e}]"

def analyze_full_text(markdown_content: str):
    """
    Calls an LLM to generate a detailed analysis of a paper from its full markdown content.
    """
    if not client:
        return "[Analysis Skipped: API client not initialized]"

    print(f"Analyzing full paper text (length: {len(markdown_content)} chars)...")
    
    prompt_template_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'analyzer_prompt.txt')
    with open(prompt_template_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # Correctly concatenate the prompt and the full paper content
    prompt = (
        prompt_template + 
        "\n\n---\n\n" +
        "请基于以上要求, 对以下论文全文内容进行分析:\n\n" +
        markdown_content
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        
        print("Sending full text analysis request to LLM API...")
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during full text analysis: {e}")
        return f"[Analysis Failed]"