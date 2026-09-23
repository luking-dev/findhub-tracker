#!/bin/sh
set -e

# Copia los secrets de Google al checkout de GoogleFindMyTools (allí los lee la librería)
if [ -f /app/auth/secrets.json ]; then
  mkdir -p /app/GoogleFindMyTools/Auth
  cp /app/auth/secrets.json /app/GoogleFindMyTools/Auth/secrets.json
  echo "[entrypoint] Auth secrets copiados a GoogleFindMyTools/Auth"
else
  echo "[entrypoint] AVISO: no existe /app/auth/secrets.json"
  echo "[entrypoint] Ejecuta en el host: python backend/scripts/auth.py  (requiere Chrome)"
fi

exec "$@"