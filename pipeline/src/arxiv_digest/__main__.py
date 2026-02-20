"""Run the full arXiv digest pipeline: python -m arxiv_digest"""

import subprocess
import sys

STEPS = [
    ("fetch", "Fetching papers from arXiv"),
    ("prefilter", "Pre-filtering by keywords/categories"),
    ("extract_latex", "Extracting LaTeX metadata"),
    ("scorer", "Scoring filtered papers"),
    ("download", "Downloading full paper texts"),
    ("reviewer", "Deep-reviewing selected papers"),
    ("digest", "Formatting digest"),
    ("deliver", "Delivering digest"),
]


def main() -> None:
    print(f"arXiv Digest Pipeline — {len(STEPS)} steps\n")
    for module, description in STEPS:
        print(f"\n{'=' * 60}\nStep: {description}\n{'=' * 60}")
        result = subprocess.run(
            [sys.executable, "-m", f"arxiv_digest.{module}"],
            check=False,
        )
        if result.returncode != 0:
            print(f"\nPipeline failed at step: {description}", file=sys.stderr)
            sys.exit(1)
    print("\nPipeline complete!")


if __name__ == "__main__":
    main()
