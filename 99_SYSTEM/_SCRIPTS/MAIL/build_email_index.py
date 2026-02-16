#!/usr/bin/env python3
"""
Index email metadata + PDF content for search.
Creates searchable index of all emails in router log + their content.
"""

import csv
import json
import re
from pathlib import Path
from datetime import datetime

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
ROUTER_LOG = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "router_log.csv"
INDEX_FILE = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "email_index.jsonl"

DEST_DIRS = {
    "KLIENTS": ROOT / "02_KLIENCI" / "_INBOX",
    "FIRMA": ROOT / "01_FIRMA",
    "CAR": ROOT / "04_CAR",
    "REVIEW": ROOT / "_REVIEW",
}


def extract_text_from_file(file_path: Path, max_chars: int = 2000) -> str:
    """Extract text from file (txt, pdf, etc)"""
    if not file_path.exists():
        return ""
    
    try:
        # Text files
        if file_path.suffix.lower() in ['.txt', '.md', '.eml']:
            return file_path.read_text(encoding='utf-8', errors='ignore')[:max_chars]
        
        # PDF files
        if file_path.suffix.lower() == '.pdf' and PDF_AVAILABLE:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages[:3]:  # First 3 pages
                    text += page.extract_text() or ""
                    if len(text) > max_chars:
                        break
            return text[:max_chars]
    except Exception as e:
        return f"[Error reading file: {type(e).__name__}]"
    
    return ""


def build_search_keywords(email: dict) -> list:
    """Extract searchable keywords from email"""
    keywords = set()
    
    # From email fields
    for field in ['subject', 'from', 'file']:
        text = email.get(field, '').lower()
        words = re.findall(r'\b\w+\b', text)
        keywords.update(words)
    
    # Extract numbers (amounts, dates, IDs)
    amounts = re.findall(r'\d+[.,]\d{2}', email.get('subject', ''))
    keywords.update(amounts)
    
    # Payment keywords
    payment_risk = email.get('payment_risk', '').lower()
    if payment_risk:
        keywords.add(f"risk:{payment_risk}")
    
    # Project type
    project_type = email.get('project_type', '').lower()
    if project_type:
        keywords.add(f"type:{project_type}")
    
    return sorted(list(keywords))


def main():
    print("Building email search index...")
    
    if not ROUTER_LOG.exists():
        print(f"Router log not found: {ROUTER_LOG}")
        return
    
    indexed = 0
    with ROUTER_LOG.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        with INDEX_FILE.open('w', encoding='utf-8') as idx:
            for row in reader:
                # Extract content from attachment
                decision = row.get('decision', '')
                meta_name = row.get('meta', '')
                file_name = row.get('file', '')
                
                # Find attachment
                content = ""
                base_dir = DEST_DIRS.get(decision)
                if base_dir:
                    file_path = base_dir / file_name
                    if file_path.exists():
                        content = extract_text_from_file(file_path, max_chars=1000)
                
                # Build index entry
                entry = {
                    "ts_utc": row.get('ts_utc', ''),
                    "subject": row.get('subject', ''),
                    "from": row.get('from', ''),
                    "decision": decision,
                    "payment_risk": row.get('payment_risk', 'n/a'),
                    "project_type": row.get('project_type', 'unknown'),
                    "keywords": build_search_keywords(row),
                    "content_preview": content[:200],
                }
                
                idx.write(json.dumps(entry, ensure_ascii=False) + '\n')
                indexed += 1
    
    print(f"Indexed: {indexed} emails")
    print(f"Index file: {INDEX_FILE}")


def search(query: str, limit: int = 10):
    """Search emails by keywords"""
    if not INDEX_FILE.exists():
        print("Index not built yet. Run main() first.")
        return
    
    query_lower = query.lower()
    results = []
    
    with INDEX_FILE.open('r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            
            # Search in keywords, subject, content
            match_score = 0
            if query_lower in entry['subject'].lower():
                match_score += 3
            if query_lower in entry['from'].lower():
                match_score += 2
            if any(query_lower in kw for kw in entry['keywords']):
                match_score += 1
            if query_lower in entry.get('content_preview', '').lower():
                match_score += 1
            
            if match_score > 0:
                results.append((match_score, entry))
    
    # Sort by score
    results.sort(key=lambda x: x[0], reverse=True)
    
    print(f"\nSearch results for '{query}' ({len(results)} matches):\n")
    for score, entry in results[:limit]:
        print(f"[{entry['payment_risk'].upper()}] {entry['subject']}")
        print(f"  From: {entry['from']}")
        print(f"  Decision: {entry['decision']} | Type: {entry['project_type']}")
        print(f"  Match score: {score}")
        print()


if __name__ == "__main__":
    main()
