import re
import unicodedata
from typing import Dict, List, Set, Tuple

# 118 Element symbols for chemistry detection
ELEMENT_SYMBOLS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og"
}

SUPER_CHAR_MAP = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-', 'ⁿ': 'n'
}

SUB_CHAR_MAP = {
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    '₊': '+', '₋': '-'
}

OPERATOR_MAP = {
    '×': r'\times',
    '÷': r'\div',
    '±': r'\pm',
    '≤': r'\leq',
    '≥': r'\geq',
    '≠': r'\neq',
    '≈': r'\approx',
    '∞': r'\infty',
    '∑': r'\sum',
    '∏': r'\prod',
    '∫': r'\int',
    '∂': r'\partial',
    '∇': r'\nabla',
    '→': r'\rightarrow',
    '⇌': r'\rightleftharpoons',
    '°': r'^{\circ}'
}

GREEK_MAP = {
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta', 'ε': r'\varepsilon',
    'θ': r'\theta', 'λ': r'\lambda', 'μ': r'\mu', 'π': r'\pi', 'ρ': r'\rho',
    'σ': r'\sigma', 'τ': r'\tau', 'φ': r'\phi', 'ω': r'\omega',
    'Δ': r'\Delta', 'Ω': r'\Omega', 'Φ': r'\Phi'
}

def normalize_unicode_and_hyphens(text: str) -> str:
    """Rule 1: Normalize Unicode (NFKC), strip soft hyphens, join words hyphenated across line breaks."""
    text = text.replace('\xad', '')
    text = re.sub(r'([a-zA-Z]+)-\n\s*([a-zA-Z]+)', r'\1\2', text)
    text = unicodedata.normalize('NFKC', text)
    return text

def convert_super_subscripts(text: str) -> str:
    """Rule 2: Convert Unicode superscripts and subscripts to LaTeX."""
    def super_replacer(match):
        chars = [SUPER_CHAR_MAP.get(c, c) for c in match.group(0)]
        return f"^{{{''.join(chars)}}}"

    def sub_replacer(match):
        chars = [SUB_CHAR_MAP.get(c, c) for c in match.group(0)]
        return f"_{{{''.join(chars)}}}"

    text = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ]+', super_replacer, text)
    text = re.sub(r'[₀₁₂₃₄₅₆₇₈₉₊₋]+', sub_replacer, text)
    return text

def convert_operators_and_greek(text: str) -> str:
    """Rule 3: Operators and symbols to LaTeX commands."""
    for op, cmd in OPERATOR_MAP.items():
        text = text.replace(op, f" {cmd} ")
    for grk, cmd in GREEK_MAP.items():
        text = text.replace(grk, f" {cmd} ")
    return text

def detect_chemistry_formulas(text: str) -> str:
    r"""Rule 4: Detect chemical formula tokens and reactions, wrap with $\ce{...}$."""
    lines = text.split('\n')
    new_lines = []
    
    for line in lines:
        if any(arrow in line for arrow in [r'\rightarrow', r'\rightleftharpoons', '->', '<=>']):
            tokens = re.findall(r'[A-Z][a-z]?', line)
            if any(t in ELEMENT_SYMBOLS for t in tokens) and not line.strip().startswith('$'):
                line = rf"$\ce{{{line.strip()}}}$"
                new_lines.append(line)
                continue
        
        def chem_replacer(match):
            token = match.group(0)
            if token.strip().startswith('$'):
                return token
            return rf"$\ce{{{token}}}$"

        chem_re = r'\b([A-Z][a-z]?(?:_\{\d+\}|\d+)?(?:[A-Z][a-z]?(?:_\{\d+\}|\d+)?)+)\b'
        line = re.sub(chem_re, chem_replacer, line)
        new_lines.append(line)
        
    return '\n'.join(new_lines)

def escape_currency(text: str) -> str:
    """Rule 6: Escape stray dollar signs that are currency (after ₹, rupee sign or Rs.)."""
    text = re.sub(r'(₹|Rs\.?|INR)\s*\$', r'\1\\$', text)
    return text

def collapse_whitespace(text: str) -> str:
    """Rule 7: Collapse whitespace while preserving markdown tables."""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith('|'):
            cleaned_lines.append(line)
        else:
            cleaned_lines.append(re.sub(r'[ \t]+', ' ', line).strip())
    
    out = '\n'.join(cleaned_lines)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()

def clean_extracted_text(text: str) -> str:
    r"""
    Applies the 7 deterministic cleaning rules in strict order:
    1. Normalize Unicode & strip soft hyphens
    2. Convert superscripts and subscripts to LaTeX
    3. Convert operators and Greek symbols to LaTeX
    4. Detect and wrap chemistry in $\ce{...}$
    5. Math wrapping checks
    6. Escape currency dollar signs
    7. Collapse whitespace and preserve Markdown tables
    """
    if not text:
        return ""
    
    t = normalize_unicode_and_hyphens(text)
    t = convert_super_subscripts(t)
    t = convert_operators_and_greek(t)
    t = detect_chemistry_formulas(t)
    t = escape_currency(t)
    t = collapse_whitespace(t)
    return t
