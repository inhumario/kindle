#!/usr/bin/env python3
"""Enviar a Kindle — sube un ebook (PDF, EPUB, MOBI…) y sale por email al Kindle de Mario.

Kindle solo acepta documentos desde direcciones aprobadas, así que el email
sale siempre desde KINDLE_FROM (alias del Gmail corporativo) hacia KINDLE_TO.

Formatos que Send-to-Kindle admite tal cual se envían directos; los que Amazon
retiró (MOBI, AZW3, FB2…) se convierten antes a EPUB con Calibre (ebook-convert).

Env: GMAIL_USER, GMAIL_APP_PASSWORD, KINDLE_FROM, KINDLE_TO.
"""
import os
import re
import smtplib
import subprocess
import tempfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

VERSION = "0.2.0"

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
KINDLE_FROM = os.environ.get("KINDLE_FROM", "mario@aromasdete.com")
KINDLE_TO = os.environ.get("KINDLE_TO", "mario_5aity2@kindle.com")

# Gmail admite 25 MB por mensaje y el base64 infla ~33 %: 18 MB de adjunto es el tope seguro.
MAX_ENVIO_MB = 18
# La entrada puede ser mayor si luego se convierte (un MOBI gordo suele adelgazar en EPUB).
MAX_SUBIDA_MB = 40

# Formatos que Send-to-Kindle acepta por email tal cual (2026).
DIRECTOS = {"pdf", "epub", "doc", "docx", "txt", "rtf", "htm", "html",
            "png", "jpg", "jpeg", "gif", "bmp"}
# Formatos de ebook que Amazon ya no acepta: se convierten a EPUB con Calibre.
CONVERTIBLES = {"mobi", "azw", "azw3", "azw4", "prc", "pdb", "fb2", "fbz",
                "lit", "lrf", "cbz", "cbr", "cb7", "cbc", "chm", "odt",
                "snb", "tcr", "rb", "pml", "htmlz", "txtz", "djvu"}

MIMES = {"pdf": ("application", "pdf"), "epub": ("application", "epub+zip"),
         "doc": ("application", "msword"),
         "docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
         "txt": ("text", "plain"), "rtf": ("application", "rtf"),
         "htm": ("text", "html"), "html": ("text", "html"),
         "png": ("image", "png"), "jpg": ("image", "jpeg"),
         "jpeg": ("image", "jpeg"), "gif": ("image", "gif"), "bmp": ("image", "bmp")}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = (MAX_SUBIDA_MB + 5) * 1024 * 1024

PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enviar a Kindle</title>
<style>
  :root {
    --verde-titulo: #0E4A31; --verde-sub: #1F7A50; --verde-filete: #35996A;
    --fondo-cab: #EAF4EE; --fondo: #F5FAF7; --borde: #C9DED3; --texto: #1F2D26;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--fondo); color: var(--texto);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.55;
    min-height: 100vh; display: flex; flex-direction: column; align-items: center;
  }
  main { width: 100%; max-width: 560px; padding: 24px 16px 40px; }
  h1 { color: var(--verde-titulo); font-size: 1.6rem; margin: 18px 0 4px; }
  .sub { color: var(--verde-sub); margin: 0 0 24px; font-size: .95rem; }
  #zona {
    background: #fff; border: 2px dashed var(--verde-filete); border-radius: 14px;
    padding: 42px 18px; text-align: center; cursor: pointer; transition: background .15s;
  }
  #zona.arrastrando, #zona:hover { background: var(--fondo-cab); }
  #zona .icono { font-size: 2.4rem; display: block; margin-bottom: 8px; }
  #zona strong { color: var(--verde-titulo); }
  #zona .pista { color: #5c6f64; font-size: .85rem; margin-top: 6px; }
  #fichero { display: none; }
  #nombre {
    display: none; margin: 14px 0 0; padding: 12px 14px; background: var(--fondo-cab);
    border: 1px solid var(--borde); border-radius: 10px; font-size: .95rem;
    overflow-wrap: anywhere;
  }
  #nombre .nota { color: #5c6f64; font-size: .85rem; display: block; margin-top: 4px; }
  button {
    width: 100%; margin-top: 16px; padding: 14px; border: 0; border-radius: 10px;
    background: var(--verde-sub); color: #fff; font-size: 1.05rem; font-weight: 600;
    cursor: pointer;
  }
  button:disabled { background: var(--borde); cursor: default; }
  #resultado {
    display: none; margin-top: 16px; padding: 14px; border-radius: 10px; font-size: .95rem;
  }
  #resultado.ok { display: block; background: var(--fondo-cab); border: 1px solid var(--verde-filete); }
  #resultado.error { display: block; background: #fdf0ee; border: 1px solid #d9a49b; color: #7a2e1f; }
  footer { color: #7d8f85; font-size: .78rem; padding: 0 16px 18px; text-align: center; }
</style>
</head>
<body>
<main>
  <h1>Enviar a Kindle</h1>
  <p class="sub">Sube un libro y llega solo al Kindle</p>
  <div id="zona">
    <span class="icono">📚</span>
    <strong>Toca aquí o arrastra un ebook</strong>
    <div class="pista">PDF, EPUB, MOBI, AZW3, FB2, DOCX… máximo {{ max_subida }} MB.<br>
    Lo que Kindle ya no admite se convierte solo a EPUB.</div>
  </div>
  <input type="file" id="fichero" accept="{{ accept }}">
  <div id="nombre"></div>
  <button id="enviar" disabled>Enviar al Kindle</button>
  <div id="resultado"></div>
</main>
<footer>inhumario · v{{ version }}</footer>
<script>
  const EXTS = {{ exts | tojson }};
  const CONVERTIBLES = {{ convertibles | tojson }};
  const zona = document.getElementById('zona');
  const input = document.getElementById('fichero');
  const nombre = document.getElementById('nombre');
  const boton = document.getElementById('enviar');
  const resultado = document.getElementById('resultado');
  let fichero = null;

  function ext(n) { const p = n.toLowerCase().split('.'); return p.length > 1 ? p.pop() : ''; }
  function elegir(f) {
    if (!f) return;
    const e = ext(f.name);
    if (!EXTS.includes(e)) { aviso('error', 'Formato .' + e + ' no soportado.'); return; }
    if (f.size > {{ max_subida }} * 1024 * 1024) {
      aviso('error', 'El fichero pesa ' + (f.size / 1048576).toFixed(1) + ' MB y el máximo es {{ max_subida }} MB.');
      return;
    }
    fichero = f;
    nombre.innerHTML = '📎 ' + f.name.replace(/</g, '&lt;') + ' (' + (f.size / 1048576).toFixed(1) + ' MB)'
      + (CONVERTIBLES.includes(e) ? '<span class="nota">Este formato se convertirá a EPUB antes de enviarlo.</span>' : '');
    nombre.style.display = 'block';
    boton.disabled = false;
    resultado.className = ''; resultado.style.display = 'none';
  }
  function aviso(tipo, texto) { resultado.className = tipo; resultado.textContent = texto; }

  zona.onclick = () => input.click();
  input.onchange = () => elegir(input.files[0]);
  ['dragover', 'dragenter'].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.add('arrastrando'); }));
  ['dragleave', 'drop'].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.remove('arrastrando'); }));
  zona.addEventListener('drop', e => elegir(e.dataTransfer.files[0]));

  boton.onclick = async () => {
    boton.disabled = true;
    const convierte = CONVERTIBLES.includes(ext(fichero.name));
    boton.textContent = convierte ? 'Convirtiendo y enviando… (puede tardar un poco)' : 'Enviando…';
    const datos = new FormData();
    datos.append('libro', fichero);
    try {
      const r = await fetch('/enviar', { method: 'POST', body: datos });
      const j = await r.json();
      if (j.ok) {
        aviso('ok', '✅ Enviado' + (j.convertido ? ' (convertido a EPUB)' : '') + '. En unos minutos aparece en el Kindle.');
        fichero = null; nombre.style.display = 'none'; input.value = '';
        boton.textContent = 'Enviar al Kindle';
      } else {
        aviso('error', '❌ ' + (j.error || 'Error al enviar.'));
        boton.textContent = 'Reintentar'; boton.disabled = false;
      }
    } catch (e) {
      aviso('error', '❌ Error de red: ' + e);
      boton.textContent = 'Reintentar'; boton.disabled = false;
    }
  };
</script>
</body>
</html>"""


@app.get("/")
def portada():
    exts = sorted(DIRECTOS | CONVERTIBLES)
    return render_template_string(
        PAGINA, max_subida=MAX_SUBIDA_MB, version=VERSION,
        exts=exts, convertibles=sorted(CONVERTIBLES),
        accept=",".join("." + e for e in exts))


def convertir_a_epub(nombre, contenido):
    """Convierte un ebook a EPUB con Calibre. Devuelve (nombre_epub, bytes)."""
    ext = nombre.rsplit(".", 1)[1].lower()
    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / f"entrada.{ext}"
        salida = Path(tmp) / "salida.epub"
        entrada.write_bytes(contenido)
        r = subprocess.run(
            ["ebook-convert", str(entrada), str(salida)],
            capture_output=True, text=True, timeout=240)
        if r.returncode != 0 or not salida.exists():
            detalle = (r.stderr or r.stdout or "").strip().splitlines()
            raise RuntimeError(detalle[-1] if detalle else f"ebook-convert devolvió {r.returncode}")
        return nombre.rsplit(".", 1)[0] + ".epub", salida.read_bytes()


@app.post("/enviar")
def enviar():
    f = request.files.get("libro") or request.files.get("pdf")
    if not f or not f.filename:
        return jsonify(ok=False, error="No ha llegado ningún fichero."), 400
    nombre = re.sub(r"[\r\n\"/\\]", "_", f.filename).strip() or "documento"
    ext = nombre.rsplit(".", 1)[1].lower() if "." in nombre else ""
    if ext not in DIRECTOS | CONVERTIBLES:
        return jsonify(ok=False, error=f"Formato .{ext} no soportado."), 400
    contenido = f.read()
    if len(contenido) > MAX_SUBIDA_MB * 1024 * 1024:
        return jsonify(ok=False, error=f"El fichero supera el máximo de {MAX_SUBIDA_MB} MB."), 400
    if ext == "pdf" and not contenido.startswith(b"%PDF"):
        return jsonify(ok=False, error="El fichero no parece un PDF válido."), 400

    convertido = False
    if ext in CONVERTIBLES:
        try:
            nombre, contenido = convertir_a_epub(nombre, contenido)
            ext, convertido = "epub", True
        except subprocess.TimeoutExpired:
            return jsonify(ok=False, error="La conversión a EPUB ha tardado demasiado."), 502
        except Exception as e:
            return jsonify(ok=False, error=f"No se ha podido convertir a EPUB: {e}"), 502

    if len(contenido) > MAX_ENVIO_MB * 1024 * 1024:
        return jsonify(ok=False, error=(
            f"El fichero a enviar pesa {len(contenido) / 1048576:.1f} MB y el máximo "
            f"que admite el email es {MAX_ENVIO_MB} MB.")), 400

    tipo, subtipo = MIMES.get(ext, ("application", "octet-stream"))
    msg = MIMEMultipart("mixed")
    msg["From"] = KINDLE_FROM
    msg["To"] = KINDLE_TO
    msg["Subject"] = nombre
    msg.attach(MIMEText("Documento enviado desde kindle.inhumario.com", "plain", "utf-8"))
    adjunto = MIMEApplication(contenido, _subtype=subtipo) if tipo == "application" \
        else MIMEApplication(contenido)
    adjunto.add_header("Content-Disposition", "attachment", filename=nombre)
    msg.attach(adjunto)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.send_message(msg, from_addr=KINDLE_FROM, to_addrs=[KINDLE_TO])
    except Exception as e:
        return jsonify(ok=False, error=f"Fallo al enviar: {type(e).__name__}: {e}"), 502
    return jsonify(ok=True, convertido=convertido)


@app.get("/salud")
def salud():
    calibre = subprocess.run(["ebook-convert", "--version"],
                             capture_output=True, text=True).stdout.strip() \
        if os.path.exists("/usr/bin/ebook-convert") else "no instalado"
    return jsonify(ok=True, version=VERSION, calibre=calibre)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8720)), debug=True)
