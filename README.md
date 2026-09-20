# Enviar a Kindle

Aplicación mínima: subes un PDF y sale por email desde `mario@aromasdete.com`
(alias del Gmail corporativo, dirección aprobada en Amazon) hacia
`mario_5aity2@kindle.com`.

- **URL**: https://kindle.inhumario.com (sin contraseña, v0.1)
- **Deploy**: EasyPanel proyecto `travelia`, servicio `kindle` (build Dockerfile
  desde este repo). Redeploy: `python3 scripts/deploy_easypanel.py deploy`.
- **Secretos**: Infisical carpeta `kindle` (`GMAIL_USER`, `GMAIL_APP_PASSWORD`,
  `KINDLE_FROM`, `KINDLE_TO`).
- Límite 18 MB por PDF (Gmail admite 25 MB de mensaje y el base64 infla un tercio).
