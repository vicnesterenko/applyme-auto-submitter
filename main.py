import asyncio
import json
import traceback

from helpers.parse_docx import load_candidate_data
from resources.values import DEFAULT_RESUME_PDF
from apply_bot import auto_submitter


async def main():
    try:
        if DEFAULT_RESUME_PDF.exists():
            DEFAULT_RESUME_PDF.unlink()

        candidate, resume_path = load_candidate_data()

        print(json.dumps(candidate, ensure_ascii=False, indent=2))
        print(f"\nResume PDF successfully created at: {resume_path}")

        await auto_submitter()
    except Exception as e:
        print(f"Помилка під час виконання: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
