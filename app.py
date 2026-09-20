#!/usr/bin/env python3
"""Enviar a Kindle — sube un PDF y sale por email al Kindle de Mario.

Kindle solo acepta documentos desde direcciones aprobadas, así que el email
sale siempre desde KINDLE_FROM (alias del Gmail corporativo) hacia KINDLE_TO.

Env: GMAIL_USER, GMAIL_APP_PASSWORD, KINDLE_FROM, KINDLE_TO.
"""
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, jsonify, render_template_string, request

VERSION = "0.1.0"

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
KINDLE_FROM = os.environ.get("KINDLE_FROM", "mario@aromasdete.com")
KINDLE_TO = os.environ.get("KINDLE_TO", "mario_5aity2@kindle.com")

# Gmail admite 25 MB por mensaje y el base64 infla ~33 %: 18 MB de PDF es el tope seguro.
MAX_PDF_MB = 18

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

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
  <p class="sub">Sube un PDF y llega solo al Kindle ({{ kindle_to }})</p>
  <div id="zona">
    <span class="icono">📄</span>
    <strong>Toca aquí o arrastra un PDF</strong>
    <div class="pista">Máximo {{ max_mb }} MB</div>
  </div>
  <input type="file" id="fichero" accept=".pdf,application/pdf">
  <div id="nombre"></div>
  <button id="enviar" disabled>Enviar al Kindle</button>
  <div id="resultado"></div>
</main>
<footer>inhumario · v{{ version }}</footer>
<script>
  const zona = document.getElementById('zona');
  const input = document.getElementById('fichero');
  const nombre = document.getElementById('nombre');
  const boton = document.getElementById('enviar');
  const resultado = document.getElementById('resultado');
  let pdf = null;

  function elegir(f) {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) { aviso('error', 'Solo se admiten PDF.'); return; }
    if (f.size > {{ max_mb }} * 1024 * 1024) {
      aviso('error', 'El PDF pesa ' + (f.size / 1048576).toFixed(1) + ' MB y el máximo es {{ max_mb }} MB.');
      return;
    }
    pdf = f;
    nombre.textContent = '📎 ' + f.name + ' (' + (f.size / 1048576).toFixed(1) + ' MB)';
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
    boton.disabled = true; boton.textContent = 'Enviando…';
    const datos = new FormData();
    datos.append('pdf', pdf);
    try {
      const r = await fetch('/enviar', { method: 'POST', body: datos });
      const j = await r.json();
      if (j.ok) {
        aviso('ok', '✅ Enviado. En unos minutos aparece en el Kindle.');
        pdf = null; nombre.style.display = 'none'; input.value = '';
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
    return render_template_string(
        PAGINA, kindle_to=KINDLE_TO, max_mb=MAX_PDF_MB, version=VERSION)


@app.post("/enviar")
def enviar():
    f = request.files.get("pdf")
    if not f or not f.filename:
        return jsonify(ok=False, error="No ha llegado ningún fichero."), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify(ok=False, error="Solo se admiten PDF."), 400
    contenido = f.read()
    if len(contenido) > MAX_PDF_MB * 1024 * 1024:
        return jsonify(ok=False, error=f"El PDF supera el máximo de {MAX_PDF_MB} MB."), 400
    if not contenido.startswith(b"%PDF"):
        return jsonify(ok=False, error="El fichero no parece un PDF válido."), 400

    msg = MIMEMultipart("mixed")
    msg["From"] = KINDLE_FROM
    msg["To"] = KINDLE_TO
    msg["Subject"] = f.filename
    msg.attach(MIMEText("Documento enviado desde kindle.inhumario.com", "plain", "utf-8"))
    adjunto = MIMEApplication(contenido, _subtype="pdf")
    adjunto.add_header("Content-Disposition", "attachment", filename=f.filename)
    msg.attach(adjunto)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.send_message(msg, from_addr=KINDLE_FROM, to_addrs=[KINDLE_TO])
    except Exception as e:
        return jsonify(ok=False, error=f"Fallo al enviar: {type(e).__name__}: {e}"), 502
    return jsonify(ok=True)


@app.get("/salud")
def salud():
    return jsonify(ok=True, version=VERSION)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8720)), debug=True)
