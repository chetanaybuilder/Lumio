"""
Evaluation Dataset for Lumio — CBSE Chemistry Sample Textbook
==============================================================
Contains 42 authentic question-to-page pairs across all 16 pages of
Chemistry_Textbook_CBSE.pdf, plus 10 extraction spot-check criteria.
"""

# 42 Question -> Expected Page(s) pairs for retrieval evaluation
RETRIEVAL_QUESTIONS = [
    # Chapter 1: Structure of the Atom (Pages 2-3)
    {
        "id": "q01",
        "question": "Who discovered the electron in 1897 using cathode ray tubes?",
        "expected_pages": [2],
    },
    {
        "id": "q02",
        "question": "What is the charge-to-mass ratio e/m of the electron measured by J. J. Thomson?",
        "expected_pages": [2],
    },
    {
        "id": "q03",
        "question": "What was Robert Millikan's oil-drop experiment and what electron charge did it determine?",
        "expected_pages": [2],
    },
    {
        "id": "q04",
        "question": "Describe Rutherford's alpha particle scattering experiment and why it led to the nuclear model.",
        "expected_pages": [2],
    },
    {
        "id": "q05",
        "question": "What are Bohr's postulates for the hydrogen atom and quantization of angular momentum?",
        "expected_pages": [2],
    },
    {
        "id": "q06",
        "question": "What is the de Broglie relation for wave-particle duality lambda = h / (m v)?",
        "expected_pages": [2],
    },
    {
        "id": "q07",
        "question": "State Heisenberg's uncertainty principle Delta x Delta p >= h / (4 pi).",
        "expected_pages": [2],
    },
    {
        "id": "q08",
        "question": "What are the four quantum numbers: principal, angular momentum, magnetic, and spin?",
        "expected_pages": [3],
    },
    {
        "id": "q09",
        "question": "Explain the Aufbau principle for filling atomic orbitals in order of increasing energy.",
        "expected_pages": [3],
    },
    {
        "id": "q10",
        "question": "State Pauli's exclusion principle regarding quantum numbers of electrons in an atom.",
        "expected_pages": [3],
    },
    {
        "id": "q11",
        "question": "What is Hund's rule of maximum multiplicity for degenerate orbitals?",
        "expected_pages": [3],
    },

    # Chapter 2: Chemical Bonding & Molecular Structure (Pages 4-5)
    {
        "id": "q12",
        "question": "Why do atoms bond according to the octet rule and potential energy lowering?",
        "expected_pages": [4],
    },
    {
        "id": "q13",
        "question": "What factors favor ionic bond formation and what is lattice energy?",
        "expected_pages": [4],
    },
    {
        "id": "q14",
        "question": "Explain valence bond theory and the difference between sigma and pi bonds.",
        "expected_pages": [4],
    },
    {
        "id": "q15",
        "question": "What are sp, sp2, and sp3 hybridization with geometry and bond angles?",
        "expected_pages": [4],
    },
    {
        "id": "q16",
        "question": "What are the assumptions of VSEPR theory regarding electron pair repulsions?",
        "expected_pages": [4],
    },
    {
        "id": "q17",
        "question": "What is the molecular geometry and bond angle of ammonia NH3 in the VSEPR table?",
        "expected_pages": [5],
    },
    {
        "id": "q18",
        "question": "What is the shape and bond angle of water H2O with two lone pairs?",
        "expected_pages": [5],
    },

    # Chapter 3: States of Matter (Pages 6-7)
    {
        "id": "q19",
        "question": "State Boyle's Law: pressure and volume relationship at constant temperature.",
        "expected_pages": [6],
    },
    {
        "id": "q20",
        "question": "State Charles's Law relating volume and absolute temperature.",
        "expected_pages": [6],
    },
    {
        "id": "q21",
        "question": "What is the Ideal Gas Equation PV = nRT and the value of R?",
        "expected_pages": [6],
    },
    {
        "id": "q22",
        "question": "What is Dalton's law of partial pressures?",
        "expected_pages": [6],
    },
    {
        "id": "q23",
        "question": "What is the van der Waals equation for real gases correcting pressure and volume?",
        "expected_pages": [6],
    },
    {
        "id": "q24",
        "question": "What are critical temperature Tc and critical pressure Pc for carbon dioxide CO2 liquefaction?",
        "expected_pages": [7],
    },

    # Chapter 4: Chemical Thermodynamics (Page 8)
    {
        "id": "q25",
        "question": "State the First Law of Thermodynamics and formula Delta U = q + w.",
        "expected_pages": [8],
    },
    {
        "id": "q26",
        "question": "Define enthalpy H = U + PV and heat of reaction at constant pressure Delta H = qp.",
        "expected_pages": [8],
    },
    {
        "id": "q27",
        "question": "State Hess's Law of constant heat summation.",
        "expected_pages": [8],
    },
    {
        "id": "q28",
        "question": "State the Second Law of Thermodynamics and entropy Delta S = qrev / T.",
        "expected_pages": [8],
    },
    {
        "id": "q29",
        "question": "What is the Gibbs free energy equation Delta G = Delta H - T Delta S and spontaneity criteria?",
        "expected_pages": [8],
    },

    # Chapter 5: Chemical Equilibrium (Pages 9-10)
    {
        "id": "q30",
        "question": "Define dynamic chemical equilibrium and the equilibrium constant Kc.",
        "expected_pages": [9],
    },
    {
        "id": "q31",
        "question": "How does the reaction quotient Q relate to the equilibrium constant K?",
        "expected_pages": [9],
    },
    {
        "id": "q32",
        "question": "State Le Chatelier's principle regarding temperature, pressure, and concentration shifts.",
        "expected_pages": [9],
    },
    {
        "id": "q33",
        "question": "What are Arrhenius, Bronsted-Lowry, and Lewis acid-base definitions?",
        "expected_pages": [9],
    },
    {
        "id": "q34",
        "question": "What is the Henderson-Hasselbalch equation for buffer solution pH?",
        "expected_pages": [10],
    },

    # Chapter 6: Redox & Electrochemistry (Pages 11-12)
    {
        "id": "q35",
        "question": "Define oxidation, reduction, reducing agents, and rules for assigning oxidation states.",
        "expected_pages": [11],
    },
    {
        "id": "q36",
        "question": "How does an electrochemical galvanic cell like the Daniell cell operate?",
        "expected_pages": [11],
    },
    {
        "id": "q37",
        "question": "What is the Nernst equation for calculating cell potential under non-standard conditions?",
        "expected_pages": [11],
    },
    {
        "id": "q38",
        "question": "State Faraday's first and second laws of electrolysis and the value of Faraday's constant F.",
        "expected_pages": [12],
    },

    # Chapter 7: Organic Chemistry (Pages 13-14)
    {
        "id": "q39",
        "question": "How are alkanes, alkenes, alkynes, and aromatic hydrocarbons classified?",
        "expected_pages": [13],
    },
    {
        "id": "q40",
        "question": "What are structural isomerism and stereoisomerism in organic chemistry?",
        "expected_pages": [13],
    },
    {
        "id": "q41",
        "question": "Explain the inductive effect (-I and +I groups) and its influence on acidity and basicity.",
        "expected_pages": [14],
    },

    # Chapter 8: Solutions & Problems (Pages 15-16)
    {
        "id": "q42",
        "question": "Define Raoult's law and the four colligative properties: boiling elevation, freezing depression, vapor lowering, osmotic pressure.",
        "expected_pages": [15],
    },
]

# 10 extraction fidelity spot checks across the 16 pages
EXTRACTION_SPOT_CHECKS = [
    {
        "page": 2,
        "title": "Structure of the Atom / Thomson & Millikan",
        "required_snippets": [
            "J. J. Thomson",
            "1.758820",
            "Millikan",
            "oil-drop",
            "Rutherford",
        ],
    },
    {
        "page": 3,
        "title": "Quantum Numbers & Aufbau",
        "required_snippets": [
            "Principal quantum number",
            "Angular momentum",
            "Aufbau",
            "Pauli",
            "Hund",
        ],
    },
    {
        "page": 4,
        "title": "Chemical Bonding & VSEPR",
        "required_snippets": [
            "octet rule",
            "lattice energy",
            "hybridization",
            "VSEPR",
        ],
    },
    {
        "page": 5,
        "title": "VSEPR Geometry Table",
        "required_snippets": [
            "Trigonal pyramidal",
            "107°",
        ],
    },
    {
        "page": 6,
        "title": "Gas Laws & Real Gases",
        "required_snippets": [
            "Boyle's Law",
            "Charles's Law",
            "PV = nRT",
            "van der Waals",
        ],
    },
    {
        "page": 8,
        "title": "Chemical Thermodynamics",
        "required_snippets": [
            "First Law of Thermodynamics",
            "Hess's Law",
            "Second Law",
            "Gibbs",
        ],
    },
    {
        "page": 9,
        "title": "Chemical Equilibrium & Le Chatelier",
        "required_snippets": [
            "Equilibrium Constant",
            "Le Chatelier",
            "Bronsted-Lowry",
        ],
    },
    {
        "page": 11,
        "title": "Redox & Nernst Equation",
        "required_snippets": [
            "Oxidation and Reduction",
            "Daniell cell",
            "Nernst",
        ],
    },
    {
        "page": 13,
        "title": "Organic Chemistry Fundamentals",
        "required_snippets": [
            "Alkanes",
            "Alkenes",
            "functional groups",
            "isomerism",
        ],
    },
    {
        "page": 15,
        "title": "Solutions & Colligative Properties",
        "required_snippets": [
            "Molarity",
            "Molality",
            "Raoult's Law",
            "colligative",
        ],
    },
]
