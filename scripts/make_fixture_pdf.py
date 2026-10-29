import argparse
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

def create_scanned_image(text="SCANNED OCR TEST PAGE - OPTICAL CHARACTER RECOGNITION"):
    img = Image.new('RGB', (800, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 750, 1050], outline=(180, 180, 180), width=2)
    draw.text((100, 200), text, fill=(20, 20, 20))
    draw.text((100, 300), "This is a scanned diagram image containing text for vision repair.", fill=(50, 50, 50))
    # Draw simple diagram
    draw.ellipse([250, 450, 550, 750], outline=(0, 0, 150), width=3)
    draw.text((320, 580), "E = mc^2", fill=(0, 0, 150))
    
    img_bytes_path = Path("temp_scanned_page.png")
    img.save(img_bytes_path, "PNG")
    return img_bytes_path

def generate_pdf(output_path: str, target_pages: int = 20):
    doc = fitz.open()
    
    # Page 1: Title & Overview (KNOWN STRING FOR VERIFICATION)
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(fitz.Point(50, 80), "VEXOVAULT GOLDEN TEST FIXTURE: CHAPTER 1 - ELECTROSTATICS", fontsize=16, fontname="helv")
    p1.insert_text(fitz.Point(50, 120), "Known String Page 1: VEXOVAULT_VERIFY_TOKEN_ALPHA_001", fontsize=11, fontname="helv")
    p1.insert_text(fitz.Point(50, 150), "Coulomb's Law states that the electrical force between two charged objects is directly proportional to the product of the quantity of charge on the objects and inversely proportional to the square of the separation distance between the two objects.", fontsize=10, fontname="helv")
    p1.insert_text(fitz.Point(50, 200), "Formula: F = (1 / (4 * pi * epsilon_0)) * (q1 * q2) / r^2", fontsize=10, fontname="helv")
    p1.insert_text(fitz.Point(50, 240), "SI unit of permittivity is C^2 N^-1 m^-2. The value of epsilon_0 is 8.854 x 10^-12 F/m.", fontsize=10, fontname="helv")

    # Page 2: Unicode superscripts & subscripts (KNOWN STRING)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text(fitz.Point(50, 80), "Known String Page 2: VEXOVAULT_VERIFY_TOKEN_BETA_002", fontsize=14, fontname="helv")
    p2.insert_text(fitz.Point(50, 120), "Unicode math symbols: x² + y² = r²", fontsize=11, fontname="helv")
    p2.insert_text(fitz.Point(50, 150), "Subscripts in chemistry: H₂O + CO₂ → H₂CO₃", fontsize=11, fontname="helv")
    p2.insert_text(fitz.Point(50, 180), "Scientific notation: 10⁻⁶ C and 1.6 × 10⁻¹⁹ C", fontsize=11, fontname="helv")
    p2.insert_text(fitz.Point(50, 210), "Operators: a ≤ b, x ≥ y, a ≠ b, α + β = γ", fontsize=11, fontname="helv")

    # Page 3: Tables and Structured Columns (KNOWN STRING)
    p3 = doc.new_page(width=595, height=842)
    p3.insert_text(fitz.Point(50, 80), "Known String Page 3: VEXOVAULT_VERIFY_TOKEN_GAMMA_003", fontsize=14, fontname="helv")
    table_text = (
        "Table 1.1: Physical Constants and Units\n"
        "| Quantity | Symbol | Value | SI Unit |\n"
        "| Permittivity of free space | epsilon_0 | 8.854 x 10^-12 | C^2 N^-1 m^-2 |\n"
        "| Elementary charge | e | 1.602 x 10^-19 | C |\n"
        "| Mass of electron | m_e | 9.109 x 10^-31 | kg |\n"
        "| Speed of light | c | 2.998 x 10^8 | m/s |\n"
    )
    p3.insert_text(fitz.Point(50, 120), table_text, fontsize=10)

    # Page 4: Two-column layout (KNOWN STRING)
    p4 = doc.new_page(width=595, height=842)
    p4.insert_text(fitz.Point(50, 80), "Known String Page 4: VEXOVAULT_VERIFY_TOKEN_DELTA_004", fontsize=14, fontname="helv")
    col1 = "Column A: Electric Field\nThe electric field E is defined as the force per unit charge exerted on a small positive test charge placed at that point in space. E = F / q_0. Field lines point outward from positive charges and inward toward negative charges."
    col2 = "Column B: Electric Potential\nThe electrostatic potential V at any point in a region of electric field is the work done in bringing a unit positive charge from infinity to that point against electrostatic forces. V = W / q."
    p4.insert_text(fitz.Point(50, 130), col1, fontsize=9, fontname="helv")
    p4.insert_text(fitz.Point(320, 130), col2, fontsize=9, fontname="helv")

    # Page 5: Worked Example & Derivation (KNOWN STRING)
    p5 = doc.new_page(width=595, height=842)
    p5.insert_text(fitz.Point(50, 80), "Known String Page 5: VEXOVAULT_VERIFY_TOKEN_EPSILON_005", fontsize=14, fontname="helv")
    p5.insert_text(fitz.Point(50, 110), "Worked Derivation: Electric Field of an Electric Dipole on the Axial Line", fontsize=12, fontname="helv")
    deriv_text = (
        "Given:\n"
        "An electric dipole consisting of two charges -q and +q separated by a distance 2a.\n"
        "Step 1: The electric field E1 at point P due to charge +q at distance (r - a) is E1 = q / (4 * pi * epsilon_0 * (r - a)^2) along BP.\n"
        "Step 2: The electric field E2 at point P due to charge -q at distance (r + a) is E2 = q / (4 * pi * epsilon_0 * (r + a)^2) along PA.\n"
        "Step 3: Since E1 and E2 act along the same line in opposite directions, net electric field E = E1 - E2.\n"
        "Step 4: E = (q / (4 * pi * epsilon_0)) * [ 1/(r - a)^2 - 1/(r + a)^2 ] = (q / (4 * pi * epsilon_0)) * [ 4ar / (r^2 - a^2)^2 ].\n"
        "Step 5: For a short dipole where r >> a, we have E_axial = (2 * p) / (4 * pi * epsilon_0 * r^3), where p = 2aq is the dipole moment.\n"
        "Result:\n"
        "The electric field varies inversely with the cube of the distance from the dipole center."
    )
    p5.insert_text(fitz.Point(50, 140), deriv_text, fontsize=9, fontname="helv")

    # Page 6: Scanned / Image Page
    img_path = create_scanned_image()
    try:
        p6 = doc.new_page(width=595, height=842)
        p6.insert_image(fitz.Rect(50, 50, 545, 792), filename=str(img_path))
    finally:
        if img_path.exists():
            img_path.unlink()

    # Repeat pages to fill target_pages
    current_pages = 6
    while current_pages < target_pages:
        p = doc.new_page(width=595, height=842)
        ch_idx = (current_pages // 10) + 1
        p.insert_text(fitz.Point(50, 50), f"Chapter {ch_idx}: Synthetic Chapter Section - Page {current_pages + 1}", fontsize=12, fontname="helv")
        sample_para = (
            f"Paragraph for synthetic benchmark on page {current_pages + 1}. "
            "Magnetic flux phi through any surface is given by the surface integral of magnetic field B. "
            "Faraday observed that whenever there is a change in magnetic flux linked with a circuit, an induced EMF is produced in the circuit. "
            "Lenz's law provides the direction of induced current: the polarity of induced EMF is such that it produces a current whose magnetic field opposes the change which produces it. "
            "In symbols: epsilon = - d(phi) / dt. The negative sign represents Lenz's law. "
        ) * 5
        p.insert_text(fitz.Point(50, 100), sample_para, fontsize=9, fontname="helv")
        current_pages += 1

    doc.save(output_path)
    doc.close()
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"Generated PDF at {output_path}: {target_pages} pages, {size_mb:.2f} MB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="fixtures/fixture_synthetic.pdf")
    parser.add_argument("--pages", type=int, default=20)
    args = parser.parse_args()
    generate_pdf(args.output, args.pages)
