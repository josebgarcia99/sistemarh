"""Evaluación de CV por lotes: lote, resultados, Excel y ZIP, permisos de lectura, consumo y móvil.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración.
"""

# ruff: noqa
import io, os, tempfile, zipfile
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS
errors = []
def login(page, email):
    page.goto(BASE + "/login")
    page.get_by_role("textbox", name="Correo", exact=True).fill(email)
    page.get_by_role("textbox", name="Contraseña", exact=True).fill(PW)
    page.get_by_role("button", name="Entrar").click()
def open_cv_tab(page, shared=False):
    page.get_by_role("link", name="Vacantes", exact=True).click()
    if shared: page.get_by_role("button", name="Compartidas conmigo").click()
    page.get_by_role("button", name="Abrir Analista de Nómina").click()
    # La guía de la vacante abre directamente el paso de los CV.
    page.get_by_role("button", name="Paso 3: Cargar y evaluar CV").click()
def docx_cv(text):
    """DOCX mínimo con texto inventado, para cargarlo como CV."""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    path = os.path.join(tempfile.mkdtemp(prefix="cv-e2e-"), f"CV {text}.docx")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{ns}"><w:body><w:p><w:r><w:t>{text}. Analista de nómina en Empresa Ficticia, 2020 a 2024.</w:t></w:r></w:p></w:body></w:document>')
    return path
with sync_playwright() as p:
    browser = p.chromium.launch(); ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True); page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: errors.append(f"{r.status} {r.request.method} {r.url.split('?')[0][-50:]}") if r.status >= 400 and "health" not in r.url else None)
    login(page, "ana@demo.test")
    page.get_by_role("link", name="Vacantes", exact=True).click(); page.get_by_role("button", name="Abrir Analista de Nómina").click()
    paso = page.get_by_role("button", name="Paso 3: Cargar y evaluar CV")
    expect(paso).to_have_attribute("aria-current", "step"); expect(paso).to_contain_text("4 CV cargados · 4 sin evaluar")
    expect(page.get_by_role("button", name="Paso 2: Prompt de evaluación")).to_contain_text("Aprobado")
    page.screenshot(path=f"{SHOTS}/cv0_pasos.png", full_page=True); print("0 la vacante muestra sus pasos, cómo va cada uno y resalta el que sigue")
    paso.click()
    expect(page.get_by_text("4 · 4 sin evaluar con este prompt")).to_be_visible(); print("1 la pestaña muestra el prompt aprobado y 4 CV sin evaluar")
    page.screenshot(path=f"{SHOTS}/cv1_antes.png", full_page=True)
    page.get_by_role("button", name="Evaluar 4 CV").click()
    expect(page.get_by_role("status").filter(has_text="terminó")).to_be_visible()
    lst = page.get_by_role("list", name="CV del lote")
    expect(lst.get_by_role("listitem")).to_have_count(4)
    expect(lst.get_by_text("No evaluable")).to_have_count(1)
    expect(page.get_by_text("4 de 4 CV procesados")).to_be_visible(); print("2 el lote se evalúa: 4 CV, uno no evaluable (escaneado)")
    lst.get_by_role("listitem").first.locator("summary").click()
    expect(lst.get_by_role("listitem").first.get_by_role("table")).to_be_visible()
    page.screenshot(path=f"{SHOTS}/cv2_resultados.png", full_page=True)
    lst.get_by_text("CV Escaneado Ficticio.pdf").click()
    expect(lst.get_by_text("No se encontró texto legible")).to_be_visible(); print("3 el detalle muestra criterios, evidencia y el motivo del no evaluable")
    with page.expect_download() as d: page.get_by_role("link", name="Descargar Reporte_Evaluacion.xlsx").click()
    xlsx = d.value.path(); assert d.value.suggested_filename == "Reporte_Evaluacion.xlsx"
    assert zipfile.is_zipfile(xlsx)
    names = []
    for label in ("Aceptados.zip", "Rechazados.zip", "No_Evaluables.zip"):
        link = page.get_by_role("link", name=f"Descargar {label}")
        if link.count():
            with page.expect_download() as d: link.click()
            z = zipfile.ZipFile(d.value.path()); names.append((label, z.namelist()))
    total = sum(len(n) - 1 for _, n in names); assert total == 4, names
    assert all("MANIFIESTO.csv" in n for _, n in names); print("4 Excel y ZIP se descargan; los ZIP suman los 4 originales con manifiesto:", [(l, len(n) - 1) for l, n in names])
    expect(page.get_by_role("button", name="Evaluar 0 CV")).to_be_disabled()
    page.get_by_role("checkbox", name="Volver a evaluar también los ya evaluados").check()
    page.get_by_role("button", name="Evaluar 4 CV").click()
    expect(page.get_by_label("Lote", exact=True).locator("option")).to_have_count(2); print("5 se puede repetir la evaluación; el lote anterior se conserva")
    # Varios CV de una vez, sin salir de la evaluación; de ahí se pasa a los candidatos
    notas = os.path.join(tempfile.mkdtemp(prefix="cv-e2e-"), "notas.txt"); open(notas, "w").write("no es un CV")
    page.get_by_label("Archivos de CV").set_input_files([docx_cv("Persona Ficticia 8"), docx_cv("Persona Ficticia 9"), notas])
    expect(page.get_by_role("status").filter(has_text="Se cargaron 2 CV")).to_be_visible()
    expect(page.get_by_role("alert").filter(has_text="notas.txt: formato no permitido")).to_be_visible()
    expect(page.get_by_text("6 · 2 sin evaluar con este prompt")).to_be_visible()
    page.screenshot(path=f"{SHOTS}/cv2b_carga.png", full_page=True)
    page.get_by_role("button", name="Ver candidatos y etapas").click()
    expect(page.get_by_role("list", name="Candidatos").get_by_role("listitem").first).to_be_visible(); print("5b se cargan 2 CV de una vez (el .txt se rechaza) y un botón lleva a los candidatos")
    # Los generados no aparecen entre los documentos de la vacante
    page.get_by_role("button", name="Volver a vacantes").click()
    page.get_by_role("button", name="Abrir Analista de Nómina").click()
    expect(page.get_by_text("Reporte_Evaluacion.xlsx")).to_have_count(0)
    expect(page.get_by_text("CV Persona Ficticia 1.pdf")).to_be_visible(); print("6 los archivos generados no se mezclan con los documentos cargados")
    # Lectura: Beto ve y descarga, no opera
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True); page2 = ctx2.new_page()
    page2.on("response", lambda r: errors.append(f"B {r.status} {r.request.method} {r.url.split('?')[0][-50:]}") if r.status >= 400 and "health" not in r.url else None)
    login(page2, "beto@demo.test"); open_cv_tab(page2, shared=True)
    expect(page2.get_by_role("link", name="Descargar Aceptados.zip")).to_be_visible()
    expect(page2.get_by_role("button", name="Evaluar", exact=False)).to_have_count(0)
    with page2.expect_download() as d: page2.get_by_role("link", name="Descargar Reporte_Evaluacion.xlsx").click()
    assert d.value.path(); print("7 con acceso de lectura se consulta y descarga, sin botones para operar")
    # Auditoría y consumo
    ctx3 = browser.new_context(viewport={"width": 1440, "height": 1000}); page3 = ctx3.new_page()
    login(page3, "admin@demo.test")
    page3.get_by_role("link", name="Auditoría", exact=True).click()
    expect(page3.get_by_text("lote_cv.terminado").first).to_be_visible()
    expect(page3.get_by_text("exportacion.generada").first).to_be_visible()
    page3.get_by_role("link", name="IA", exact=True).click()
    usage = page3.get_by_role("region", name="Consumo y costos de este mes")
    expect(usage.get_by_role("cell", name="6", exact=True).first).to_be_visible(); print("8 auditoría registra lotes y exportaciones; el consumo muestra 6 llamadas")
    page3.screenshot(path=f"{SHOTS}/cv3_consumo.png", full_page=True)
    # Móvil
    m = browser.new_context(viewport={"width": 390, "height": 844}); pm = m.new_page()
    login(pm, "ana@demo.test"); expect(pm.get_by_role("button", name="Cerrar sesión")).to_be_visible(); pm.goto(BASE + "/vacantes"); pm.get_by_role("button", name="Abrir Analista de Nómina").click()
    pm.get_by_role("button", name="Paso 3: Cargar y evaluar CV").click()
    expect(pm.get_by_role("list", name="CV del lote")).to_be_visible()
    overflow = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    pm.screenshot(path=f"{SHOTS}/cv4_movil.png", full_page=True); print("9 móvil: desbordamiento horizontal =", overflow)
    browser.close()
print("errores:", sorted(set(errors)))
