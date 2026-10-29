import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def build_syllabus():
    math12_topics = [
        {
            'chapter_no': 1, 'chapter_title': 'Relations and Functions', 'weightage': 4.0,
            'topics': ['Types of relations: reflexive, symmetric, transitive and equivalence relations', 'One to one and onto functions', 'Composite functions and inverse of a function']
        },
        {
            'chapter_no': 2, 'chapter_title': 'Inverse Trigonometric Functions', 'weightage': 4.0,
            'topics': ['Definition, range, domain, principal value branch', 'Graphs of inverse trigonometric functions', 'Elementary properties of inverse trigonometric functions']
        },
        {
            'chapter_no': 3, 'chapter_title': 'Matrices', 'weightage': 5.0,
            'topics': ['Concept, notation, order, equality, types of matrices', 'Zero and identity matrix, transpose of a matrix, symmetric and skew symmetric matrices', 'Operation on matrices: addition and multiplication with scalar', 'Invertible matrices and uniqueness of inverse']
        },
        {
            'chapter_no': 4, 'chapter_title': 'Determinants', 'weightage': 5.0,
            'topics': ['Determinant of a square matrix up to 3x3', 'Minors, co-factors and applications of determinants in area of triangle', 'Adjoint and inverse of a square matrix', 'Consistency and solutions of linear equations by matrix method']
        },
        {
            'chapter_no': 5, 'chapter_title': 'Continuity and Differentiability', 'weightage': 9.0,
            'topics': ['Continuity and differentiability, derivative of composite functions, chain rule', 'Derivative of inverse trigonometric functions', 'Derivative of implicit functions and logarithmic differentiation', 'Parametric derivatives and second order derivatives']
        },
        {
            'chapter_no': 6, 'chapter_title': 'Applications of Derivatives', 'weightage': 7.0,
            'topics': ['Rate of change of quantities', 'Increasing and decreasing functions', 'Maxima and minima using first and second derivative tests', 'Real life optimization problems']
        },
        {
            'chapter_no': 7, 'chapter_title': 'Integrals', 'weightage': 10.0,
            'topics': ['Integration as inverse of differentiation', 'Integration by substitution, partial fractions and parts', 'Evaluation of standard integrals', 'Fundamental Theorem of Calculus and properties of definite integrals']
        },
        {
            'chapter_no': 8, 'chapter_title': 'Applications of the Integrals', 'weightage': 5.0,
            'topics': ['Area under simple curves, lines, parabolas, and circles']
        },
        {
            'chapter_no': 9, 'chapter_title': 'Differential Equations', 'weightage': 4.0,
            'topics': ['Order and degree of differential equations', 'Method of separation of variables', 'Homogeneous differential equations of first order', 'Linear differential equations dy/dx + Py = Q']
        },
        {
            'chapter_no': 10, 'chapter_title': 'Vectors', 'weightage': 7.0,
            'topics': ['Vectors and scalars, magnitude and direction cosines', 'Addition of vectors and multiplication by scalar', 'Dot product and projection of vector on line', 'Cross product of vectors']
        },
        {
            'chapter_no': 11, 'chapter_title': 'Three-Dimensional Geometry', 'weightage': 7.0,
            'topics': ['Direction cosines and direction ratios', 'Cartesian and vector equation of a line', 'Shortest distance between skew lines', 'Angle between lines']
        },
        {
            'chapter_no': 12, 'chapter_title': 'Linear Programming', 'weightage': 5.0,
            'topics': ['Terminology, objective function and constraints', 'Graphical method of solution for two variables', 'Feasible and infeasible regions and optimization']
        },
        {
            'chapter_no': 13, 'chapter_title': 'Probability', 'weightage': 8.0,
            'topics': ['Conditional probability and multiplication rule', 'Independent events and total probability', 'Bayes theorem', 'Random variable and probability distribution']
        }
    ]

    math10_topics = [
        {
            'chapter_no': 1, 'chapter_title': 'Real Numbers', 'weightage': 6.0,
            'topics': ['Fundamental Theorem of Arithmetic', 'Proofs of irrationality of sqrt(2), sqrt(3), sqrt(5)']
        },
        {
            'chapter_no': 2, 'chapter_title': 'Polynomials', 'weightage': 4.0,
            'topics': ['Zeros of a polynomial', 'Relationship between zeros and coefficients of quadratic polynomials']
        },
        {
            'chapter_no': 3, 'chapter_title': 'Pair of Linear Equations in Two Variables', 'weightage': 6.0,
            'topics': ['Graphical method of solution, consistency and inconsistency', 'Algebraic solutions: substitution and elimination method', 'Simple situational word problems']
        },
        {
            'chapter_no': 4, 'chapter_title': 'Quadratic Equations', 'weightage': 6.0,
            'topics': ['Standard form ax^2 + bx + c = 0', 'Solutions by factorization and quadratic formula', 'Relationship between discriminant and nature of roots']
        },
        {
            'chapter_no': 5, 'chapter_title': 'Arithmetic Progressions', 'weightage': 4.0,
            'topics': ['nth term of an AP', 'Sum of first n terms of an AP and application in solving daily life problems']
        },
        {
            'chapter_no': 6, 'chapter_title': 'Triangles', 'weightage': 9.0,
            'topics': ['Definitions, examples, counter examples of similar triangles', 'Basic Proportionality Theorem (Thales theorem) and proof', 'Criteria for similarity of triangles (AAA, SSS, SAS)']
        },
        {
            'chapter_no': 7, 'chapter_title': 'Coordinate Geometry', 'weightage': 6.0,
            'topics': ['Distance formula between two points', 'Section formula (internal division)']
        },
        {
            'chapter_no': 8, 'chapter_title': 'Introduction to Trigonometry', 'weightage': 8.0,
            'topics': ['Trigonometric ratios of acute angle of a right-angled triangle', 'Values of trigonometric ratios of 30, 45, 60 degrees', 'Trigonometric identity sin^2 A + cos^2 A = 1']
        },
        {
            'chapter_no': 9, 'chapter_title': 'Some Applications of Trigonometry', 'weightage': 4.0,
            'topics': ['Heights and distances: angle of elevation and angle of depression (30, 45, 60)']
        },
        {
            'chapter_no': 10, 'chapter_title': 'Circles', 'weightage': 6.0,
            'topics': ['Tangent to a circle at point of contact', 'Length of tangents drawn from external point are equal']
        },
        {
            'chapter_no': 11, 'chapter_title': 'Areas Related to Circles', 'weightage': 4.0,
            'topics': ['Area of sectors and segments of a circle with central angles 60, 90, 120']
        },
        {
            'chapter_no': 12, 'chapter_title': 'Surface Areas and Volumes', 'weightage': 6.0,
            'topics': ['Surface areas and volumes of combinations of cubes, cuboids, spheres, hemispheres, cones, cylinders']
        },
        {
            'chapter_no': 13, 'chapter_title': 'Statistics', 'weightage': 7.0,
            'topics': ['Mean, median and mode of grouped data (bimodal situation avoided)']
        },
        {
            'chapter_no': 14, 'chapter_title': 'Probability', 'weightage': 4.0,
            'topics': ['Classical definition of probability and simple problems on single events']
        }
    ]

    physics12_topics = [
        {
            'chapter_no': 1, 'chapter_title': 'Electric Charges and Fields', 'weightage': 4.0,
            'topics': ['Coulombs law and superposition principle', 'Electric field lines and dipole in uniform electric field', 'Gauss theorem and applications to infinite wire, plane sheet, spherical shell']
        },
        {
            'chapter_no': 2, 'chapter_title': 'Electrostatic Potential and Capacitance', 'weightage': 4.0,
            'topics': ['Electric potential and potential energy of system of charges', 'Capacitors and capacitance, parallel plate capacitor with dielectric', 'Energy stored in a capacitor']
        },
        {
            'chapter_no': 3, 'chapter_title': 'Current Electricity', 'weightage': 8.0,
            'topics': ['Electric current, drift velocity and Ohms law', 'V-I characteristics, electrical resistivity and conductivity', 'Kirchhoffs rules and Wheatstone bridge']
        },
        {
            'chapter_no': 4, 'chapter_title': 'Moving Charges and Magnetism', 'weightage': 5.0,
            'topics': ['Biot-Savart law and application to circular loop', 'Amperes circuital law and solenoid', 'Force on moving charge in magnetic field and Lorentz force', 'Moving coil galvanometer and conversion to ammeter/voltmeter']
        },
        {
            'chapter_no': 5, 'chapter_title': 'Magnetism and Matter', 'weightage': 4.0,
            'topics': ['Bar magnet as equivalent solenoid, magnetic field lines', 'Magnetic properties of materials: dia, para and ferromagnetic substances']
        },
        {
            'chapter_no': 6, 'chapter_title': 'Electromagnetic Induction', 'weightage': 4.0,
            'topics': ['Faradays laws of induction, induced EMF and current', 'Lenzs law and conservation of energy', 'Self and mutual induction']
        },
        {
            'chapter_no': 7, 'chapter_title': 'Alternating Current', 'weightage': 4.0,
            'topics': ['Peak and RMS value of alternating current/voltage', 'Reactance, impedance, LCR series circuit and resonance', 'Power in AC circuits and AC generator/transformer']
        },
        {
            'chapter_no': 8, 'chapter_title': 'Electromagnetic Waves', 'weightage': 3.0,
            'topics': ['Displacement current, electromagnetic spectrum and characteristics']
        },
        {
            'chapter_no': 9, 'chapter_title': 'Ray Optics and Optical Instruments', 'weightage': 9.0,
            'topics': ['Refraction at spherical surfaces, lens makers formula', 'Refraction through a prism and dispersion', 'Microscopes and astronomical telescopes']
        },
        {
            'chapter_no': 10, 'chapter_title': 'Wave Optics', 'weightage': 9.0,
            'topics': ['Huygens principle and proof of reflection and refraction', 'Interference of light and Youngs double slit experiment', 'Diffraction due to a single slit']
        },
        {
            'chapter_no': 11, 'chapter_title': 'Dual Nature of Radiation and Matter', 'weightage': 5.0,
            'topics': ['Photoelectric effect and Einsteins photoelectric equation', 'de Broglie relation and wave nature of matter']
        },
        {
            'chapter_no': 12, 'chapter_title': 'Atoms', 'weightage': 3.5,
            'topics': ['Alpha-particle scattering experiment, Rutherfords model', 'Bohr model of hydrogen atom, energy levels and line spectra']
        },
        {
            'chapter_no': 13, 'chapter_title': 'Nuclei', 'weightage': 3.5,
            'topics': ['Composition and size of nucleus, mass-energy relation', 'Nuclear binding energy, nuclear fission and fusion']
        },
        {
            'chapter_no': 14, 'chapter_title': 'Semiconductor Electronics', 'weightage': 7.0,
            'topics': ['Energy bands in conductors, semiconductors and insulators', 'p-n junction diode: I-V characteristics in forward and reverse bias', 'Diode as a rectifier']
        }
    ]

    def format_syllabus(class_lvl, sub, ch_list, src):
        items = []
        ord_c = 1
        prefix = sub[:4].lower()
        for ch in ch_list:
            ch_key = f"cbse_{class_lvl}_{prefix}_ch{ch['chapter_no']}"
            items.append({
                'topic_key': ch_key,
                'class_level': class_lvl,
                'subject': sub,
                'chapter_no': ch['chapter_no'],
                'chapter_title': ch['chapter_title'],
                'parent_key': None,
                'title': ch['chapter_title'],
                'ordinal': ord_c,
                'weightage_marks': ch['weightage'],
                'syllabus_year': '2024-25',
                'source_url': src
            })
            ord_c += 1
            for sub_idx, top in enumerate(ch['topics'], start=1):
                top_key = f"{ch_key}_t{sub_idx}"
                items.append({
                    'topic_key': top_key,
                    'class_level': class_lvl,
                    'subject': sub,
                    'chapter_no': ch['chapter_no'],
                    'chapter_title': ch['chapter_title'],
                    'parent_key': ch_key,
                    'title': top,
                    'ordinal': ord_c,
                    'weightage_marks': round(ch['weightage'] / len(ch['topics']), 2),
                    'syllabus_year': '2024-25',
                    'source_url': src
                })
                ord_c += 1
        return items

    src = 'https://cbseacademic.nic.in/curriculum_2025.html'
    m12 = format_syllabus(12, 'Mathematics', math12_topics, src)
    m10 = format_syllabus(10, 'Mathematics', math10_topics, src)
    p12 = format_syllabus(12, 'Physics', physics12_topics, src)

    out_dir = BASE_DIR / 'backend' / 'seed' / 'syllabus'
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / 'cbse_12_maths.json', 'w', encoding='utf-8') as f:
        json.dump({'class_level': 12, 'subject': 'Mathematics', 'year': '2024-25', 'topics': m12}, f, indent=2)

    with open(out_dir / 'cbse_10_maths.json', 'w', encoding='utf-8') as f:
        json.dump({'class_level': 10, 'subject': 'Mathematics', 'year': '2024-25', 'topics': m10}, f, indent=2)

    with open(out_dir / 'cbse_12_physics.json', 'w', encoding='utf-8') as f:
        json.dump({'class_level': 12, 'subject': 'Physics', 'year': '2024-25', 'topics': p12}, f, indent=2)

    print(f"Generated: m12={len(m12)}, m10={len(m10)}, p12={len(p12)} topics.")

if __name__ == '__main__':
    build_syllabus()
