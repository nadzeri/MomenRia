import os
import argparse
import hashlib
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main():
    parser = argparse.ArgumentParser(description="Run an isolated, synthetic MomenRia browser-test server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--payments", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="momenria-e2e-") as directory:
        os.environ.update({
            "DJANGO_SETTINGS_MODULE": "momenria.settings", "APP_ENV": "test", "DJANGO_DEBUG": "true",
            "DATABASE_URL": "", "SQLITE_PATH": str(Path(directory) / "db.sqlite3"),
            "PUBLIC_ACCESS": "false", "APP_BASE_URL": f"http://127.0.0.1:{args.port}",
            "ALLOWED_HOSTS": "127.0.0.1,localhost", "DJANGO_SECRET_KEY": "isolated-e2e-secret-not-for-production",
            "PRIVATE_MEDIA_ROOT": str(Path(directory) / "media"), "TOMBSTONE_ROOT": str(Path(directory) / "tombstones"),
            "AI_GATEWAY_MODE": "fake", "PAYMENT_PROVIDER": "fake" if args.payments else "disabled", "PAYMENT_ENV": "sandbox", "PAYMENT_CHECKOUT_ENABLED": str(args.payments).lower(),
            "NINE_ROUTER_API_KEY": "", "NINE_ROUTER_BASE_URL": "", "PAYMENT_SERVER_KEY": "",
            "ADMISSION_ENABLED": "true", "DAILY_BUDGET_IDR": "100000", "ALLOW_UNBOUNDED_TEST_BUDGET": "false",
            "STORAGE_MIN_FREE_BYTES": "0", "STORAGE_MAX_USED_PERCENT": "100", "RESULT_FONT_PATH": "",
            "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend", "LOG_LEVEL": "ERROR",
        })
        import django
        django.setup()
        from django.core.management import call_command
        from allauth.account.models import EmailAddress
        from accounts.models import User
        from PIL import Image

        call_command("migrate", verbosity=0)
        call_command("seed_catalog", test_publish=True, verbosity=0)
        call_command("prepare_character_templates", model="fake-test", gateway_path="/images/generations", portrait_max_cost_idr=1500, sheet_max_cost_idr=500, generated_sheets=True, test_publish=True, verbosity=0)
        names = ["desktop", "mobile", "outsider", "graduate-desktop", "graduate-mobile", "character-desktop", "character-mobile", "competitive-desktop", "competitive-mobile", "payments-desktop", "payments-mobile", "paymentstates-desktop", "paymentstates-mobile"]
        titles = re.findall(r"test\('([^']+)',", (ROOT / "tests/e2e/launch.spec.js").read_text())
        for title in titles:
            suffix = hashlib.sha256(title.encode()).hexdigest()[:10]
            names.extend(f"launch-{surface}-{suffix}" for surface in ("desktop", "mobile"))
        for name in names:
            user = User.objects.create_user(f"{name}@example.com", "Portrait-test-2026!", email_verified=True)
            EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        fixtures = ROOT / "tests/e2e/generated"
        fixtures.mkdir(parents=True, exist_ok=True)
        with Image.open(ROOT / "static/app/assets/lebaran.png") as image:
            for name, x, y in (("left", .391, .241), ("right", .646, .308)):
                cx, cy = x * image.width, y * image.height
                image.crop((int(cx - 180), int(cy - 180), int(cx + 180), int(cy + 180))).convert("RGB").save(fixtures / f"{name}.jpg", quality=95)
        worker = subprocess.Popen([sys.executable, "manage.py", "runworker"], cwd=ROOT)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False, verbosity=0)
        finally:
            worker.terminate()
            worker.wait(timeout=5)


if __name__ == "__main__":
    main()
