import subprocess
from pathlib import Path

# Get files from git ls-files
git_res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
git_files = set(f.strip() for f in git_res.stdout.strip().splitlines() if f.strip())

# Read AUDIT.md
audit_text = Path("AUDIT.md").read_text(encoding="utf-8")

missing = []
covered = 0
for f in git_files:
    if f"`{f}`" in audit_text:
        covered += 1
    else:
        missing.append(f)

total = len(git_files)
pct = (covered / total) * 100 if total > 0 else 0

print(f"=== AUDIT.md COVERAGE REPORT ===")
print(f"Total git tracked files: {total}")
print(f"Covered in AUDIT.md:     {covered}")
print(f"Missing from AUDIT.md:   {len(missing)}")
print(f"Coverage Percentage:     {pct:.2f}%")

if missing:
    print("\nMissing files:")
    for m in missing:
        print(f"  - {m}")
    exit(1)
else:
    print("\nVERIFICATION: 100% COVERAGE VERIFIED. Every tracked file is in AUDIT.md.")
