import pandas as pd
from openai import OpenAI
import json
import os
from dotenv import load_dotenv

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Set this to: 'OLLAMA', 'OPENAI', or 'GEMINI'
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
    - "names": [Extract specific people or organizations mentioned, e.g., 'Liz Evans', 'Hostos']
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
        return json.loads(response.choices[0].message.content)
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
        # Search across Name, Notes, and Organizations
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
    if matches.empty:
        return "I couldn't find any data to summarize for that topic."

    # Build Rich Context
    context_text = ""

    # We pass all matches now because Gemini's context window can handle the full Database query!
    for idx, row in matches.iterrows():
        context_text += f"""
        ---
        CONTACT: {row.get('Contact Name', 'Unknown')} ({row.get('Campus', 'Unknown')})
        ROLE: {row.get('Role/Title', '')} | {row.get('Program/Org Affiliation', '')}
        RAW NOTE: "{row.get('Notes / Insights', '')}"
        CHALLENGES: "{row.get('Needs / Challenges', 'N/A')}"
        TAGS: {row.get('Civic Domains', '')}
        """

    system_prompt = "You are a CUNY Civic Insight Analyst. Answer the user's question using the provided database records."
    user_prompt = f"""
    User Question: "{query}"

    Instructions:
    - Answer based ONLY on the data below.
    - Cite specific people, campuses, or programs to build cross-campus connections.
    - If the raw notes mention specific challenges or details, make sure to highlight them to the user.

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
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating insight: {e}"