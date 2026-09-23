#!/usr/bin/env python3
"""Autenticación única con Google Find Hub. Requiere Google Chrome instalado.

Genera <repo>/auth/secrets.json con los tokens de sesión de tu cuenta.
Solo hay que ejecutarlo una vez; luego el backend funciona headless.

Uso:
    python backend/scripts/auth.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / ".tools"
GFMT = TOOLS / "GoogleFindMyTools"
DEST = ROOT / "auth" / "secrets.json"


def ensure_gfmt() -> None:
    if not (GFMT / "main.py").exists():
        print("[*] Clonando GoogleFindMyTools...")
        GFMT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/leonboe1/GoogleFindMyTools.git", str(GFMT)],
            check=True,
        )
    print(f"[*] GoogleFindMyTools listo en: {GFMT}")


def main() -> None:
    print("=" * 60)
    print("Autenticación única con Google Find Hub")
    print("=" * 60)
    ensure_gfmt()

    print("[*] Instalando dependencias del host...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(GFMT / "requirements.txt")],
        check=True,
    )

    sys.path.insert(0, str(GFMT))

    try:
        from Auth.auth_flow import request_oauth_account_token_flow
    except ImportError:
        print("[!] No se pudo importar GoogleFindMyTools. Verifica el checkout en .tools/")
        sys.exit(1)

    print("[*] Abriendo Chrome para iniciar sesión con tu cuenta de Google...")
    try:
        request_oauth_account_token_flow()
    except Exception as e:
        print(f"[!] Fallo de autenticación: {e}")

    src = GFMT / "Auth" / "secrets.json"
    if not src.exists():
        print("[!] No se generó Auth/secrets.json. Revisa la salida anterior.")
        sys.exit(1)

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DEST)
    print(f"[ OK ] Secrets guardados en {DEST}")
    print("       Reinicia el backend:  docker compose up -d --build backend")


if __name__ == "__main__":
    main()