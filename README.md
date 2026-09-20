# Enviar a Kindle

Aplicación mínima: subes un ebook (PDF, EPUB, MOBI, AZW3, FB2, DOCX…) y sale
por email desde `mario@aromasdete.com` (alias del Gmail corporativo, dirección
aprobada en Amazon) hacia el Kindle de Mario. Los formatos que Send-to-Kindle
ya no acepta (MOBI y demás) se convierten antes a EPUB con Calibre
(`ebook-convert`, incluido en la imagen Docker).

- **URL**: https://kindle.inhumario.com (sin contraseña, v0.1)
- **Deploy**: EasyPanel proyecto `travelia`, servicio `kindle` (build Dockerfile
  desde este repo). Redeploy: `python3 scripts/deploy_easypanel.py deploy`.
- **Secretos**: Infisical carpeta `kindle` (`GMAIL_USER`, `GMAIL_APP_PASSWORD`,
  `KINDLE_FROM`, `KINDLE_TO`).
- Límite 18 MB por adjunto (Gmail admite 25 MB de mensaje y el base64 infla un
  tercio); la subida admite hasta 40 MB si el fichero luego se convierte.
