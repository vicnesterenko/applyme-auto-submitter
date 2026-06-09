from pathlib import Path


FONT_URL_FOR_PDF = "https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/fonts/DejaVuSans/DejaVuSans.ttf"

JOBS_URLS = [
    "https://jobs.lever.co/aledade/6fd40837-f0c2-4e8a-b22c-ae94e9145732",
    "https://jobs.lever.co/raptv/57dfc4b3-7853-401b-9887-459b23a58457",
    "https://jobs.lever.co/padsplit/8a9e818f-13a3-4591-8351-b1910fd971a8/apply",
    "https://jobs.lever.co/skillerszone/9322615b-cd4c-4d21-b414-a086a6311819",
    "https://jobs.lever.co/theathletic/12025a5f-02f4-4f03-802a-3d7466e2eb13",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MAIN_DIR = Path(__file__).resolve().parent
PROFILE_DOCX = MAIN_DIR / "profile_candidate.docx"
RESUME_DOCX = MAIN_DIR / "resume.docx"
DEFAULT_RESUME_PDF = MAIN_DIR / "pdf_resume" / "resume.pdf"
LOCAL_DOWNLOAD_PATH = MAIN_DIR / "DejaVuSans.ttf"
SCREENSHOTS_DIR = MAIN_DIR / "screenshots_auto_apply"