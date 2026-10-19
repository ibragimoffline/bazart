"""Celery worker importi barcha SQLAlchemy mapper'larini sozlay oladimi.

NEGA ALOHIDA JARAYON: pytest jarayonida ilova (va barcha modellar) allaqachon yuklangan —
xato ko'rinmaydi. Worker esa faqat `app.tasks.*` ni yuklaydi; model ro'yxatdan o'tmasa
(masalan Deal -> Offer) beat vazifalarining birinchi ORM so'rovi yiqiladi. Bu aynan
shunday bo'lgan — toza interpreter'da tekshiramiz.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_worker_task_modules_configure_all_mappers() -> None:
    code = (
        "import app.tasks.scheduled, app.tasks.notifications\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr[-2000:]
