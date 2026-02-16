"""
Process training emails from _REPLIES_TRAINING and evaluate with Claude
Creates evaluation report with payment_risk, project_type, urgency, quality
"""

import json
import email
from pathlib import Path
from client_evaluator import evaluate_client_email

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
TRAINING_DIR = ROOT / "_REPLIES_TRAINING" / "2025" / "MSG"
OUTPUT_FILE = ROOT / "00_INBOX" / "TRAINING_EVALUATIONS.json"

def extract_email_body(eml_path: Path) -> str:
    """Extract plain text body from .eml file"""
    with open(eml_path, 'r', encoding='utf-8') as f:
        msg = email.message_from_file(f)
    
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='ignore')
    
    # Return first 500 chars for preview
    return body[:500] if body else ""

def process_all_training_emails():
    """Process all training emails and create evaluation report"""
    
    results = []
    
    # Find all message folders
    msg_folders = sorted([d for d in TRAINING_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')])
    
    print(f"Found {len(msg_folders)} training emails\n")
    
    for folder in msg_folders:
        meta_file = folder / "meta.json"
        eml_file = folder / "reply.eml"
        
        if not meta_file.exists() or not eml_file.exists():
            print(f"⚠️ Skipping {folder.name} - missing files")
            continue
        
        # Read metadata
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        # Extract email body
        body_preview = extract_email_body(eml_file)
        
        subject = meta.get('subject', '')
        print(f"📧 {folder.name}")
        print(f"   Subject: {subject}")
        print(f"   To: {meta.get('to', 'N/A')}")
        
        # Evaluate with Claude
        evaluation = evaluate_client_email(subject, body_preview)
        
        # Create result entry
        result = {
            'folder': folder.name,
            'date': meta.get('date_utc'),
            'subject': subject,
            'to': meta.get('to'),
            'body_preview': body_preview[:200],
            'pdf_count': meta.get('pdf_count', 0),
            'evaluation': evaluation
        }
        
        results.append(result)
        
        print(f"   Risk: {evaluation.get('payment_risk')}, Type: {evaluation.get('project_type')}, Quality: {evaluation.get('quality')}\n")
    
    # Save results
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(results)} evaluations to {OUTPUT_FILE}")
    
    # Summary statistics
    risk_counts = {}
    type_counts = {}
    
    for r in results:
        ev = r['evaluation']
        risk = ev.get('payment_risk', 'unknown')
        ptype = ev.get('project_type', 'unknown')
        
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        type_counts[ptype] = type_counts.get(ptype, 0) + 1
    
    print("\n=== SUMMARY ===")
    print(f"Payment Risk Distribution: {risk_counts}")
    print(f"Project Type Distribution: {type_counts}")

if __name__ == "__main__":
    process_all_training_emails()
