"""
Process JSONL training data - sample diverse emails and evaluate with Claude
Selects variety: short/long, different subjects, different recipients
"""

import json
import random
from pathlib import Path
from client_evaluator import evaluate_client_email

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
JSONL_FILE = ROOT / "_COLLECT_DROP" / "REPLIES_TRAINING" / "replies_2023_2026.jsonl"
OUTPUT_FILE = ROOT / "00_INBOX" / "JSONL_EVALUATIONS.json"

def load_jsonl_emails(limit=30):
    """Load emails from JSONL, sample diverse set"""
    emails = []
    
    with open(JSONL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                emails.append(json.loads(line))
    
    print(f"Total emails in JSONL: {len(emails)}")
    
    # Sample strategy: diverse subjects and body lengths
    diverse_sample = []
    
    # Get short emails (< 200 chars)
    short = [e for e in emails if len(e.get('body', '')) < 200]
    diverse_sample.extend(random.sample(short, min(5, len(short))))
    
    # Get medium emails (200-1000 chars)
    medium = [e for e in emails if 200 <= len(e.get('body', '')) < 1000]
    diverse_sample.extend(random.sample(medium, min(10, len(medium))))
    
    # Get long emails (> 1000 chars)
    long = [e for e in emails if len(e.get('body', '')) >= 1000]
    diverse_sample.extend(random.sample(long, min(10, len(long))))
    
    # Get emails with specific keywords
    keywords = ['wycena', 'umowa', 'faktur', 'zapytanie', 'termin', 'prośba']
    for kw in keywords:
        matching = [e for e in emails if kw.lower() in e.get('subject', '').lower()]
        if matching:
            diverse_sample.append(random.choice(matching))
    
    # Deduplicate by message_id
    seen = set()
    unique = []
    for e in diverse_sample:
        mid = e.get('message_id')
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(e)
    
    return unique[:limit]

def process_jsonl_emails():
    """Process sampled emails and evaluate"""
    
    emails = load_jsonl_emails(limit=30)
    
    print(f"\nProcessing {len(emails)} sampled emails...\n")
    
    results = []
    
    for i, email in enumerate(emails, 1):
        subject = email.get('subject', '')
        body = email.get('body', '')
        body_preview = body[:500] if body else ""
        
        print(f"[{i}/{len(emails)}] {subject[:50]}")
        
        # Evaluate
        evaluation = evaluate_client_email(subject, body_preview)
        
        result = {
            'message_id': email.get('message_id'),
            'date': email.get('dt_utc', '')[:10],
            'subject': subject,
            'to': email.get('to'),
            'from': email.get('from'),
            'body_length': len(body),
            'body_preview': body_preview[:200],
            'evaluation': evaluation
        }
        
        results.append(result)
        
        ev = evaluation
        print(f"   → Risk: {ev.get('payment_risk')}, Type: {ev.get('project_type')}, Quality: {ev.get('quality')}")
    
    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved {len(results)} evaluations to {OUTPUT_FILE}")
    
    # Statistics
    risk_counts = {}
    type_counts = {}
    quality_counts = {}
    
    for r in results:
        ev = r['evaluation']
        risk_counts[ev.get('payment_risk', 'unknown')] = risk_counts.get(ev.get('payment_risk', 'unknown'), 0) + 1
        type_counts[ev.get('project_type', 'unknown')] = type_counts.get(ev.get('project_type', 'unknown'), 0) + 1
        quality_counts[ev.get('quality', 'unknown')] = quality_counts.get(ev.get('quality', 'unknown'), 0) + 1
    
    print("\n=== STATISTICS ===")
    print(f"Payment Risk: {risk_counts}")
    print(f"Project Type: {type_counts}")
    print(f"Quality: {quality_counts}")

if __name__ == "__main__":
    process_jsonl_emails()
