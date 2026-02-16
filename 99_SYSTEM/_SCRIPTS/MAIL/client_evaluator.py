"""
AI Client Evaluator for Archiwum 3.0
Assesses email inquiries using Claude API based on CORE LOGIKA
Author: Archiwum System
Date: 2026-02-02
"""

import json
import os
from pathlib import Path

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

def evaluate_client_email_mock(subject: str, body_preview: str) -> dict:
    """Simple heuristic evaluator without API (fallback)"""
    keywords = {
        'wycena': 'major', 'projekt': 'major', 'umowa': 'major',
        'faktury': 'administrative', 'rachunk': 'administrative',
        'zapytanie': 'minor', 'pytanie': 'minor', 'informacja': 'minor'
    }
    
    subject_lower = subject.lower()
    project_type = 'consultation'
    for kw, ptype in keywords.items():
        if kw in subject_lower:
            project_type = ptype
            break
    
    urgency = 'urgent' if any(w in subject_lower for w in ['termin', 'pilne', 'szybko', 'asap']) else 'normal'
    length = len(body_preview)
    quality = 'clear' if length > 50 else ('needs_clarification' if length > 20 else 'vague')
    payment_risk = 'medium' if project_type == 'major' else 'low'
    
    return {
        'payment_risk': payment_risk,
        'project_type': project_type,
        'urgency': urgency,
        'quality': quality,
        '_method': 'mock'
    }

# Few-shot examples (from real AlisMeble emails)
EXAMPLES = [
    {
        "subject": "Wycena",
        "body_preview": "Zapoznałem się z projektami. Wstępna wycena zabudowy: ok. 8000-12000 PLN. Materiały: Blum, Egger. Termin: ok. 4 tygodnie.",
        "ground_truth": {
            "payment_risk": "low",
            "project_type": "major",
            "urgency": "normal",
            "quality": "clear"
        }
    },
    {
        "subject": "Faktury",
        "body_preview": "Chyba tyle było",
        "ground_truth": {
            "payment_risk": "n/a",
            "project_type": "administrative",
            "urgency": "normal",
            "quality": "clear"
        }
    },
    {
        "subject": "ile kosztuje szafa",
        "body_preview": "ile kosztuje szafa? ile będzie czekać?",
        "ground_truth": {
            "payment_risk": "high",
            "project_type": "unknown",
            "urgency": "normal",
            "quality": "vague"
        }
    },
]

def evaluate_client_email(subject: str, body_preview: str) -> dict:
    """
    Evaluate a client email using Claude API with few-shot prompting.
    Falls back to heuristic if API key unavailable.
    
    Returns dict with keys:
    - payment_risk: low | medium | high | n/a
    - project_type: major | minor | consultation | administrative
    - urgency: urgent | normal | backlog
    - quality: clear | needs_clarification | vague
    """
    
    # Fallback if no API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    # Try reading from secrets file if not in environment
    if not api_key:
        key_file = ROOT / "99_SYSTEM" / "_SECRETS" / "anthropic_key.txt"
        if key_file.exists():
            api_key = key_file.read_text().strip()
    
    if not api_key or not ANTHROPIC_AVAILABLE or api_key == "sk-ant-...":
        return evaluate_client_email_mock(subject, body_preview)
    client = Anthropic(api_key=api_key)
    
    # Build few-shot examples into the prompt
    examples_text = "\n".join([
        f"Subject: {ex['subject']}\nBody: {ex['body_preview']}\n" +
        f"Evaluation: {json.dumps(ex['ground_truth'])}\n"
        for ex in EXAMPLES
    ])
    
    prompt = f"""Jesteś ekspertem w ocenie emaili dla biznesu meblowego w Polsce.

Oceń email klienta na podstawie tematu i zawartości. Użyj JSON bez wyjaśnień.

Parametry (wartości):
1. payment_risk: 'low' (projekt + detalicość), 'medium' (nieznane), 'high' (marketing), 'n/a' (nie klient)
2. project_type: 'major' (duży), 'minor' (mały), 'consultation' (pytanie), 'administrative' (system)
3. urgency: 'urgent' (PILNE!), 'normal' (zwyczajne), 'backlog' (kiedyś)
4. quality: 'clear' (zrozumiałe), 'needs_clarification' (niejasne), 'vague' (bardzo tumannie)

Przykłady:
{examples_text}

Email do oceny:
Subject: {subject}
Body: {body_preview}

Odpowiedź (TYLKO JSON, bez słów):
"""

    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON response
    try:
        result_text = response.content[0].text.strip()
        # Try to extract JSON from response (in case there's extra text)
        if result_text.startswith('{'):
            return json.loads(result_text)
        else:
            # Try to find JSON object in response
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(result_text[start:end])
            else:
                return {"error": "parse_failed", "raw": result_text}
    except json.JSONDecodeError as e:
        return {"error": f"json_error: {str(e)}", "raw": response.content[0].text}
    except Exception as e:
        return {"error": f"unexpected: {str(e)}", "raw": response.content[0].text}


def main():
    """Test evaluator on sample emails."""
    
    print("=== Client Evaluator Test ===\n")
    
    test_emails = [
        ("Wycena", "Zapoznałem się z projektami. Wstępna wycena: ok. 8000-12000 PLN."),
        ("ile kosztuje", "ile kosztuje szafa?"),
        ("Re: Faktury", "Chyba tyle było"),
    ]
    
    for subject, body in test_emails:
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        result = evaluate_client_email(subject, body)
        print(f"Evaluation: {json.dumps(result, indent=2)}\n")


if __name__ == "__main__":
    main()
