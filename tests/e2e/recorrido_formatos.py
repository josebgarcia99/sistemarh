"""Formatos de la empresa: el perfil se llena al subir el formato en Excel; Gemini
aparece como proveedor y el estudio socioeconómico usa la plantilla SGC.F3.RH.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración. El
formato que se sube se genera aquí con datos inventados.
"""

# ruff: noqa
import os, subprocess, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS

API = Path(__file__).resolve().parents[2] / "apps" / "api"
book = Path(tempfile.mkdtemp(prefix="reclu-formato-")) / "SGC.F15.RH. Perfil de puesto.xlsx"
book.write_bytes(subprocess.check_output(
    [os.environ["E2E_API_PYTHON"], "-c",
     "import sys; from app.tests.support.sample_files import profile_format_xlsx; "
     "sys.stdout.buffer.write(profile_format_xlsx())"], cwd=API))

errors = []
def watch(page, tag=""):
    page.on("pageerror", lambda e: errors.append(tag + str(e)))
    page.on("response", lambda r: errors.append(f"{tag}{r.status} {r.request.method} {r.url.split('?')[0][-50:]}") if r.status >= 400 and "health" not in r.url else None)
def login(page, email):
    page.goto(BASE + "/login")
    page.get_by_role("textbox", name="Correo", exact=True).fill(email)
    page.get_by_role("textbox", name="Contraseña", exact=True).fill(PW)
    page.get_by_role("button", name="Entrar").click()

with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1440, "height": 1000}); watch(page)
    login(page, "ana@demo.test")
    page.get_by_role("link", name="Vacantes", exact=True).click()
    page.get_by_role("button", name="Abrir Auxiliar Contable").click()
    page.get_by_role("button", name="Perfil, prompt y evaluación de CV").click()
    expect(page.get_by_text("Todavía no hay perfil")).to_be_visible()
    # 1. Subir el formato llena los campos, sin IA.
    page.get_by_label("Formato del perfil").set_input_files(str(book))
    expect(page.get_by_role("status").filter(has_text="Se leyó el formato de la empresa")).to_be_visible()
    expect(page.get_by_label("Nombre del puesto")).to_have_value("Analista de Nómina")
    expect(page.get_by_label("Área o departamento")).to_have_value("Recursos Humanos")
    expect(page.get_by_label("Fecha de actualización")).to_have_value("2026-10-05")
    levels = page.get_by_role("group", name="Formación académica")
    expect(levels.get_by_label("Licenciatura")).to_be_checked(); expect(levels.get_by_label("Maestría")).not_to_be_checked()
    expect(page.get_by_label("Requisitos indispensables (uno por línea)")).to_have_value("\n".join([
        "Cálculo de nómina quincenal", "Cuotas IMSS e INFONAVIT", "Cálculo de ISR",
        "Timbrado de recibos", "Finiquitos y liquidaciones", "Manejo de incidencias"]))
    expect(page.get_by_label("Actividad 1", exact=True)).to_have_value("Registrar incidencias.")
    expect(page.get_by_label("Periodicidad de la actividad 1")).to_have_value("Diaria")
    expect(page.get_by_label("KPI 1", exact=True)).to_have_value("Nóminas pagadas a tiempo")
    notices = page.get_by_role("list", name="Avisos de la lectura")
    expect(notices.get_by_text("edad mínima 25")).to_be_visible()
    expect(notices.get_by_text("Quincenal")).to_be_visible()
    expect(page.get_by_text("Todavía no hay perfil")).to_be_visible(); print("1 al subir el formato en Excel se llenan los campos; la edad no se copia y se avisa")
    page.screenshot(path=f"{SHOTS}/formato1_perfil.png", full_page=True)
    # 2. La persona completa lo que faltaba y guarda.
    page.get_by_label("Periodicidad de la actividad 2").select_option("Semanal")
    page.get_by_role("button", name="Guardar perfil").click()
    expect(page.get_by_role("status").filter(has_text="versión 1")).to_be_visible()
    expect(page.get_by_role("list", name="Versiones del perfil").get_by_text("Formato de la empresa")).to_be_visible(); print("2 se guarda como versión 1, marcada como leída del formato")
    # 3. Del perfil sale el prompt con un criterio por requisito indispensable.
    page.get_by_role("button", name="Prompt de evaluación").click()
    page.get_by_role("button", name="Generar borrador desde el perfil").click()
    expect(page.get_by_role("list", name="Criterios").get_by_role("listitem")).to_have_count(6); print("3 el prompt sale del perfil: 6 criterios, uno por requisito indispensable")
    # 4. Un archivo que no es un formato aceptado se rechaza con su motivo.
    page.get_by_role("button", name="Perfil de puesto").click()
    bad = book.with_name("perfil.txt"); bad.write_text("no es un formato")
    page.get_by_label("Formato del perfil").set_input_files(str(bad))
    expect(page.get_by_role("alert").filter(has_text="Formato no permitido")).to_be_visible(); print("4 un archivo de otro tipo se rechaza con su motivo")
    # 5. Administrador: Gemini como proveedor y la plantilla del estudio.
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}); admin = ctx.new_page(); watch(admin, "A ")
    login(admin, "admin@demo.test"); admin.get_by_role("link", name="IA", exact=True).click()
    card = admin.get_by_role("region", name="Google Gemini")
    expect(card).to_be_visible(); expect(admin.get_by_role("region", name="Anthropic")).to_be_visible(); expect(admin.get_by_role("region", name="OpenAI")).to_be_visible()
    admin.screenshot(path=f"{SHOTS}/formato2_gemini.png", full_page=True); print("5 Google Gemini aparece como tercer proveedor en la pantalla de IA")
    admin.get_by_role("link", name="Formularios", exact=True).click()
    admin.get_by_role("button", name="SGC.F3.RH. Estudio socioeconómico").click()
    expect(admin.get_by_label("Sección 19", exact=True)).to_have_value("Ratificación y firmas")
    expect(admin.get_by_label("Columnas del campo 1 de la sección 13")).to_have_value("Nombre,Edad,Parentesco,Escolaridad,Ocupación,Ingreso mensual")
    admin.screenshot(path=f"{SHOTS}/formato3_estudio.png", full_page=True); print("6 la plantilla del estudio es el formato SGC.F3.RH, con sus 19 secciones y sus tablas")
    browser.close()
print("errores:", sorted(set(errors)))
