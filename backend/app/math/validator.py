import re
import json
import subprocess
from pathlib import Path
from typing import Tuple, List, Dict, Any

MATH_DIR = Path(__file__).resolve().parent

# Regex for detecting math spans
DISPLAY_MATH_RE = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')
CE_MATH_RE = re.compile(r'\\ce\{(.+?)\}')

NODE_VALIDATOR_SCRIPT = """
const fs = require('fs');
let katex;
try {
    katex = require('katex');
    require('katex/contrib/mhchem');
} catch (e) {
    try {
        katex = require('./backend/app/math/katex.js');
    } catch (e2) {
        katex = require('./katex.js');
    }
}

const inputData = JSON.parse(fs.readFileSync(0, 'utf-8'));
const results = [];

for (const rawExpr of inputData) {
    const expr = (rawExpr || '').trim();
    if (!expr) {
        results.push({ valid: true, expr, error: null });
        continue;
    }
    try {
        katex.renderToString(expr, {
            throwOnError: true,
            strict: false
        });
        results.push({ valid: true, expr, error: null });
    } catch (err) {
        results.push({ valid: false, expr, error: err.message });
    }
}

console.log(JSON.stringify(results));
"""

def extract_math_spans(text: str) -> List[str]:
    """Extracts all math spans from markdown text."""
    if not text or ("$" not in text and "\\ce{" not in text):
        return []
    
    spans = []
    # 1. Display math $$...$$
    for match in DISPLAY_MATH_RE.finditer(text):
        spans.append(match.group(1).strip())
    
    # Remove display math before looking for inline math to avoid collisions
    cleaned_text = DISPLAY_MATH_RE.sub('', text)
    
    # 2. Inline math $...$
    for match in INLINE_MATH_RE.finditer(cleaned_text):
        spans.append(match.group(1).strip())
        
    return spans

def validate_expressions_batch(expressions: List[str]) -> List[Dict[str, Any]]:
    """Validates a batch of LaTeX expressions using KaTeX + mhchem via Node."""
    if not expressions:
        return []
        
    try:
        proc = subprocess.Popen(
            ["node", "-e", NODE_VALIDATOR_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        stdout, stderr = proc.communicate(input=json.dumps(expressions), timeout=20)
        if proc.returncode == 0 and stdout.strip():
            return json.loads(stdout)
        else:
            return [{"valid": False, "expr": e, "error": stderr or "Unknown validator error"} for e in expressions]
    except Exception as e:
        fallback_results = []
        for expr in expressions:
            valid = expr.count("{") == expr.count("}") and expr.count("(") == expr.count(")")
            fallback_results.append({
                "valid": valid,
                "expr": expr,
                "error": None if valid else f"Bracket mismatch: {str(e)}"
            })
        return fallback_results

def validate_math_text(text: str) -> Tuple[bool, List[str], int]:
    """
    Validates all math expressions in markdown text.
    Returns:
        (is_valid, error_list, span_count)
    """
    spans = extract_math_spans(text)
    if not spans:
        return True, [], 0
        
    results = validate_expressions_batch(spans)
    errors = [f"KaTeX Error in '{r['expr']}': {r['error']}" for r in results if not r["valid"]]
    is_valid = len(errors) == 0
    return is_valid, errors, len(spans)
