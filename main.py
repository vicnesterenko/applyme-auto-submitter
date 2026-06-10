import json
import traceback

from helpers.parse_docx import load_candidate_data
from resources.values import DEFAULT_RESUME_PDF

from apply_bot import main as run_bot


def main():
    try:
        if DEFAULT_RESUME_PDF.exists():
            DEFAULT_RESUME_PDF.unlink()

        candidate, resume_path = load_candidate_data()

        print(json.dumps(candidate, ensure_ascii=False, indent=2))
        print(f"\nResume PDF successfully created at: {resume_path}")

        run_bot()

    except Exception as e:
        print(f"Execution failed with error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()