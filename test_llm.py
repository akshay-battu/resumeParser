"""
Quick test script - tests the Gemini API key and model, then does a mini resume parse.
Run from the project root: python test_llm.py
"""
import os
import sys

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

api_key = os.getenv("GEMINI_API_KEY", "")
model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

print(f"Model: {model_name}")
print(f"API Key starts with: {api_key[:10]}..." if api_key else "ERROR: No API key found!")

if not api_key:
    sys.exit(1)

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    import json

    print("\n--- Test 1: Simple hello ---")
    llm = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_name,
        temperature=0.1,
    )
    response = llm.invoke([HumanMessage(content="Say hello in one sentence.")])
    print(f"Response: {response.content}")
    print("Basic API call works!\n")

except Exception as e:
    print(f"Basic API call FAILED: {e}")
    sys.exit(1)

try:
    print("--- Test 2: JSON resume parse with sample data ---")
    llm_json = ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model_name,
        temperature=0.1,
        response_mime_type="application/json",
    )

    sample_resume = """
John Doe
Software Engineer at TechCorp Inc.
Email: john.doe@example.com | Phone: +1-555-123-4567

SKILLS: Python, JavaScript, React, Docker, Kubernetes

EXPERIENCE:
TechCorp Inc. - Senior Software Engineer (2021-present)
- Led backend microservices development

EDUCATION:
B.S. Computer Science, MIT, 2018
"""

    prompt = """Extract structured candidate information from this resume text.
For each field, include a confidence score (0-1) reflecting how certain you are.

RESUME TEXT:
""" + sample_resume + """

Respond with valid JSON only. Schema:
{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "company": "string or null",
  "designation": "string or null",
  "skills": ["string"],
  "confidence": {
    "name": 0.0-1.0,
    "email": 0.0-1.0,
    "phone": 0.0-1.0,
    "company": 0.0-1.0,
    "designation": 0.0-1.0,
    "skills": 0.0-1.0
  }
}"""

    response = llm_json.invoke([HumanMessage(content=prompt)])
    text = response.content
    print(f"Raw response: {text[:500]}")

    data = json.loads(text)
    print(f"\nJSON parse SUCCESS!")
    print(f"  Name: {data.get('name')} (confidence: {data.get('confidence', {}).get('name')})")
    print(f"  Email: {data.get('email')} (confidence: {data.get('confidence', {}).get('email')})")
    print(f"  Phone: {data.get('phone')} (confidence: {data.get('confidence', {}).get('phone')})")
    print(f"  Company: {data.get('company')} (confidence: {data.get('confidence', {}).get('company')})")
    print(f"  Designation: {data.get('designation')} (confidence: {data.get('confidence', {}).get('designation')})")
    print(f"  Skills: {data.get('skills', [])}")

except Exception as e:
    print(f"JSON resume parse FAILED: {e}")
    import traceback
    traceback.print_exc()
