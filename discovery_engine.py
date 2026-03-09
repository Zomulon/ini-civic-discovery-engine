import pandas as pd
from openai import OpenAI
import json
import os
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
load_dotenv()
PROVIDER = 'GEMINI'

if PROVIDER == 'OLLAMA':
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    MODEL_NAME = "llama3"
elif PROVIDER == 'OPENAI':
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    MODEL_NAME = "gpt-4o-mini"
elif PROVIDER == 'GEMINI':
    client = OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GEMINI_API_KEY")
    )
    MODEL_NAME = "gemini-2.5-flash"


def parse_discovery_query(query):
    system_prompt = "You are a Civic Discovery Agent. You MUST output a valid JSON object."

    user_prompt = f"""
    Translate this query into search terms.
    QUERY: "{query}"

    Available keys:
    - "names": [Extract specific people or organizations mentioned. Strip punctuation and possessives like 's.]
    - "domains": ['Criminal Justice', 'Environment', 'Public Health', 'Higher Education']
    - "communities": ['Latinx', 'Bronx', 'Immigrants', 'Indigenous', 'Students']
    - "campus": ['Hunter', 'Queens', 'York', 'John Jay', 'LaGuardia']
    - "capabilities": ['Mentorship', 'Advocacy', 'Funding', 'Research']

    JSON EXAMPLE: {{"names": ["Liz Evans"], "domains": ["Public Health"]}}
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        # Robust JSON cleaning for Gemini responses
        raw_content = response.choices[0].message.content.strip()
        if raw_content.startswith('```json'):
            raw_content = raw_content[7:-3].strip()
        elif raw_content.startswith('```'):
            raw_content = raw_content[3:-3].strip()

        return json.loads(raw_content)
    except Exception as e:
        print(f"⚠️ LLM Parsing Error: {e}")
        return {}


def search_civic_network(query, df):
    filters = parse_discovery_query(query)
    results = df.copy()

    col_map = {
        "domains": "Civic Domains",
        "communities": "Communities Served",
        "campus": "Campus",
        "capabilities": "Capabilities / Expertise"
    }

    if not filters:
        return pd.DataFrame(), {}

    # Handle standard category filters
    for key, values in filters.items():
        if key == "names": continue

        target_col = col_map.get(key)
        if target_col and target_col in df.columns and values:
            pattern = '|'.join(values)
            results = results[results[target_col].fillna('').str.contains(pattern, case=False)]

    # Handle keyword/name search across the primary database fields
    if "names" in filters and filters["names"]:
        pattern = '|'.join(filters["names"])
        results['search_text'] = results['Contact Name'].fillna('') + " " + results['Notes / Insights'].fillna(
            '') + " " + results['Program/Org Affiliation'].fillna('')
        mask = results['search_text'].str.contains(pattern, case=False, na=False)
        results = results[mask]
        results = results.drop(columns=['search_text'])

    return results, filters


def generate_civic_insight(query, matches):
    """
    Takes the filtered data and generates a natural language answer
    using the RAW NOTES and METADATA from the Database.
    """

    # 1. Helpful guidance text for broad or unanswerable queries
    guidance_text = """Could you please provide more context or specify what you're looking for? For instance:

* Are you interested in finding a specific individual or organization?
* Do you have a particular topic or area of focus in mind (e.g., education, healthcare, social justice)?
* Are you seeking information on a specific CUNY campus or department?
* Do you have a specific goal or objective in mind (e.g., finding a mentor, seeking resources, exploring career opportunities)?

Once I have a better understanding of your inquiry, I'll do my best to provide a helpful response using the provided database records."""

    # 2. If no data matched at all (Empty Quick Search), return the guide immediately
    if matches.empty:
        return guidance_text

    # Build Rich Context
    context_text = ""
    for idx, row in matches.iterrows():
        context_text += f"""
        ---
        CONTACT: {row.get('Contact Name', 'Unknown')} ({row.get('Campus', 'Unknown')})
        ROLE: {row.get('Role/Title', '')} | {row.get('Program/Org Affiliation', '')}
        RAW NOTE: "{row.get('Notes / Insights', '')}"
        CHALLENGES: "{row.get('Needs / Challenges', 'N/A')}"
        TAGS: {row.get('Civic Domains', '')}
        """

    # 3. Instruct the AI to scan everything and use the guide if the question is too broad
    system_prompt = "You are a CUNY Civic Insight Analyst. You are given a massive database dump. You MUST scan the ENTIRE text below to find the answer."

    user_prompt = f"""
    User Question: "{query}"

    Instructions:
    - Answer based ONLY on the data below.
    - Cite specific people, campuses, or programs to build cross-campus connections.
    - If the exact answer is found, summarize it clearly.
    - IF the user's question is too broad, too vague, or if the exact answer is NOT found in the database, DO NOT guess. Reply EXACTLY with this text:

    {guidance_text}

    RELEVANT DATA:
    {context_text}
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating insight: {e}"