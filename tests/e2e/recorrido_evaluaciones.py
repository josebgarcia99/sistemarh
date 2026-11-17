"""Evaluaciones posteriores: prueba técnica, entrevista, psicometría, estudio, síntesis y datos sensibles.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración.
"""

# ruff: noqa
import io, os, re, subprocess, tempfile, zipfile
from pathlib import Path
from openpyxl import load_workbook
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS
# Fotografía inventada (un rectángulo de color) para adjuntarla al estudio.
FOTO = os.path.join(tempfile.mkdtemp(prefix="reclu-foto-"), "localizacion.jpg"); Image.new("RGB", (800, 600), (120, 150, 180)).save(FOTO)
# Otras dos fotografías inventadas, para agregarlas como adicionales.
PATIO = os.path.join(os.path.dirname(FOTO), "patio.jpg"); Image.new("RGB", (640, 480), (150, 170, 140)).save(PATIO)
COCINA = os.path.join(os.path.dirname(FOTO), "cocina.png"); Image.new("RGB", (640, 480), (190, 170, 150)).save(COCINA)
# Formato del estudio lleno (inventado), para adjuntarlo en el propio estudio.
FORMATO = os.path.join(os.path.dirname(FOTO), "Estudio lleno ficticio.docx")
with zipfile.ZipFile(FORMATO, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
    z.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Estudio socioeconómico ficticio. Fecha de aplicación: 10 de noviembre de 2026.</w:t></w:r></w:p></w:body></w:document>')
# Formato en blanco del estudio (inventado, con la misma estructura que el de la empresa).
EN_BLANCO = os.path.join(os.path.dirname(FOTO), "SGC.F3.RH en blanco ficticio.xlsx")
Path(EN_BLANCO).write_bytes(subprocess.check_output(
    [os.environ["E2E_API_PYTHON"], "-c",
     "import sys; from app.tests.support.study_format import study_format_xlsx; "
     "sys.stdout.buffer.write(study_format_xlsx())"], cwd=Path(__file__).resolve().parents[2] / "apps" / "api"))
errors = []
def login(page, email):
    page.goto(BASE + "/login")
    page.get_by_role("textbox", name="Correo", exact=True).fill(email)
    page.get_by_role("textbox", name="Contraseña", exact=True).fill(PW)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("button", name="Cerrar sesión")).to_be_visible()
def watch(page, tag=""):
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: errors.append(f"{tag}{r.status} {r.request.method} {r.url.split('?')[0][-40:]}") if r.status >= 400 and "health" not in r.url else None)
def open_person(page, shared=False):
    page.get_by_role("link", name="Vacantes", exact=True).click()
    if shared: page.get_by_role("button", name="Compartidas conmigo").click()
    page.get_by_role("button", name="Abrir Analista de Nómina").click()
    page.get_by_role("button", name="Candidatos y etapas").click()
    page.get_by_role("list", name="Candidatos").get_by_role("button", name="Persona Ficticia 3").click()
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1440, "height": 1000}); watch(page)
    login(page, "ana@demo.test")
    page.get_by_role("link", name="Vacantes", exact=True).click(); page.get_by_role("button", name="Abrir Analista de Nómina").click()
    page.get_by_role("button", name="Paso 1: Perfil de puesto").click(); page.get_by_role("button", name="Evaluación de CV").click()
    page.get_by_role("button", name="Evaluar 4 CV").click(); expect(page.get_by_role("status").filter(has_text="terminó")).to_be_visible()
    page.get_by_role("button", name="Volver a vacantes").click()
    open_person(page)
    sec = page.get_by_role("region", name="Evaluaciones posteriores")
    # 1. Prueba técnica con rúbrica
    sec.get_by_role("button", name="Registrar evaluación").click()
    sec.get_by_label("Tipo de evaluación").select_option("PRUEBA_TECNICA"); sec.get_by_label("Tipo de prueba").fill("Excel")
    sec.get_by_role("button", name="Registrar", exact=True).click()
    sec.get_by_role("button", name="Agregar criterio").click()
    sec.get_by_label("Criterio 1", exact=True).fill("Fórmulas"); sec.get_by_label("Puntos obtenidos del criterio 1").fill("3"); sec.get_by_label("Puntos posibles del criterio 1").fill("4")
    sec.get_by_label("Mínimo aprobatorio (0 a 100, opcional)").fill("70"); sec.get_by_label("Estado").select_option("REALIZADA")
    sec.get_by_role("button", name="Guardar", exact=True).click()
    expect(sec.get_by_text("75 de 100").first).to_be_visible(); expect(sec.get_by_text("alcanza el mínimo")).to_be_visible(); print("1 prueba técnica: la calificación (75 de 100) la calcula el sistema con la rúbrica")
    # 2. Entrevista con conclusión humana y resumen de IA
    sec.get_by_role("button", name="Registrar evaluación").click()
    sec.get_by_label("Tipo de evaluación").select_option("ENTREVISTA"); sec.get_by_label("Quién entrevista").fill("Gerente Ficticio")
    sec.get_by_role("button", name="Registrar", exact=True).click()
    sec.get_by_label("Retroalimentación del gerente").fill("Explica con claridad sus procesos.")
    sec.get_by_label("Estado").last.select_option("REALIZADA")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("alert").filter(has_text="conclusión")).to_be_visible()
    sec.get_by_label("Conclusión de quien entrevistó").fill("Recomiendo continuar."); sec.get_by_label("Fecha").last.fill("2026-11-09")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("status").filter(has_text="Evaluación guardada")).to_be_visible()
    sec.get_by_role("button", name="Organizar con IA").click()
    expect(sec.get_by_role("region", name="Resumen de la IA")).to_contain_text("Competencia simulada"); print("2 entrevista: exige la conclusión humana; la IA solo organiza lo anotado")
    # 3. Psicometría con documento cifrado y validación profesional
    sec.get_by_role("button", name="Registrar evaluación").click()
    sec.get_by_label("Tipo de evaluación").select_option("PSICOMETRIA"); sec.get_by_label("Instrumento").fill("Prueba Ficticia X")
    sec.get_by_role("button", name="Registrar", exact=True).click()
    sec.get_by_label("Documento", exact=True).select_option(label="Reporte psicométrico ficticio.docx")
    sec.get_by_label("Estado").last.select_option("VALIDADA")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("alert").filter(has_text="profesional")).to_be_visible()
    sec.get_by_label("Profesional que la interpretó").fill("Psic. Laura Ficticia"); sec.get_by_label("Resultado documentado").fill("Escala A: percentil 70.")
    sec.get_by_label("Interpretación del profesional").fill("Dentro de lo esperado.")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("status").filter(has_text="Evaluación guardada")).to_be_visible()
    sec.get_by_role("button", name="Resumir e interpretar con IA").click()
    psico = sec.get_by_role("region", name="Resumen de la IA").last
    expect(psico).to_contain_text("Resultado simulado"); expect(psico).to_contain_text("Qué significa, según el reporte"); expect(psico).to_contain_text("Preguntas para la siguiente etapa")
    print("3 psicometría: validar exige al profesional; la IA resume el reporte cifrado, explica lo que dice y propone preguntas")
    # 4. Estudio socioeconómico con digitalización
    sec.get_by_role("button", name="Registrar evaluación").click()
    sec.get_by_label("Tipo de evaluación").select_option("ESTUDIO_SOCIOECONOMICO")
    sec.get_by_role("button", name="Registrar", exact=True).click()
    # El formato lleno se adjunta en el propio estudio y queda elegido para leerlo.
    sec.get_by_label("Adjuntar el formato del estudio").set_input_files(FORMATO)
    expect(sec.get_by_role("status").filter(has_text="Archivo adjuntado")).to_be_visible()
    expect(sec.get_by_label("Formato del estudio (Excel, PDF, Word o escaneado)", exact=True).locator("option:checked")).to_have_text("Estudio lleno ficticio.docx")
    sec.get_by_role("button", name="Leer el formato con IA").click()
    expect(sec.get_by_role("status").filter(has_text="todavía no se ha guardado")).to_be_visible()
    expect(sec.get_by_text("Leído por la IA").first).to_be_visible()
    v = sec.get_by_role("checkbox", name="Fecha de aplicación: verificado"); expect(v).not_to_be_checked(); v.check()
    # 4b. Fotografía del estudio: se adjunta ahí mismo y la IA propone una descripción
    foto = "Fotografía: fachada de la vivienda"
    sec.get_by_label(foto, exact=True).select_option(label="Fachada ficticia.jpg")
    sec.get_by_role("button", name=f"Describir con IA: {foto}").click()
    desc = sec.get_by_label(f"Descripción de lo que se observa: {foto}")
    expect(desc).to_have_value(re.compile("Descripción simulada")); expect(sec.get_by_text("Descripción propuesta por la IA")).to_be_visible()
    desc.fill("Fachada de dos niveles, pintura clara y portón metálico."); expect(sec.get_by_text("Descripción propuesta por la IA")).to_have_count(0)
    sec.get_by_label("Adjuntar archivo: Fotografía: localización").set_input_files(FOTO)
    expect(sec.get_by_text("Archivo adjuntado")).to_be_visible(); expect(sec.get_by_label("Fotografía: localización", exact=True)).to_have_value(re.compile(".+")); print("4b fotos: se elige o se adjunta una foto; la IA propone la descripción y la persona la corrige")
    # 4c. Fotografías adicionales: varias de una vez, con título y descripción de la IA
    extra = sec.get_by_role("group", name="Fotografías adicionales")
    extra.get_by_label("Agregar fotografías adicionales").set_input_files([PATIO, COCINA])
    expect(extra.get_by_role("status").filter(has_text="2 fotografías agregadas")).to_be_visible()
    expect(extra.get_by_role("listitem")).to_have_count(2)
    extra.get_by_label("Título de la fotografía adicional 1").fill("Patio trasero")
    extra.get_by_role("button", name="Describir con IA: fotografía adicional 1").click()
    expect(extra.get_by_label("Descripción de lo que se observa: fotografía adicional 1")).to_have_value(re.compile("Descripción simulada"))
    extra.get_by_label("Descripción de lo que se observa: fotografía adicional 2").fill("Cocina con estufa y alacena.")
    extra.screenshot(path=f"{SHOTS}/f6_5_fotos_adicionales.png")
    print("4c fotos adicionales: se agregan dos, una la describe la IA y otra la persona")
    sec.get_by_label("Estado", exact=True).last.select_option("EN_PROCESO")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("status").filter(has_text="Evaluación guardada")).to_be_visible(); print("4 estudio: la IA llena campos sin verificar; la persona marca lo verificado")
    expect(extra.get_by_role("listitem")).to_have_count(2)
    page.screenshot(path=f"{SHOTS}/f6_1_evaluaciones.png", full_page=True)
    # 5. Expediente por etapas y síntesis
    dossier = page.get_by_role("region", name="Expediente por etapas")
    expect(dossier.get_by_text("Prueba técnica: Realizada")).to_be_visible()
    # La síntesis ya se generó sola al registrar los resultados de las evaluaciones.
    syn = dossier.get_by_role("region", name="Síntesis"); expect(syn).to_be_visible()
    dossier.get_by_role("button", name="Generar una síntesis nueva").click(); expect(dossier.get_by_text("Síntesis lista.")).to_be_visible()
    expect(syn).to_contain_text("Hechos documentados"); expect(syn).to_contain_text("pruebas psicométricas validadas")
    expect(syn).to_contain_text("Preguntas sugeridas para la siguiente etapa")
    historial = dossier.get_by_label(re.compile("Síntesis guardadas")); expect(historial).to_be_visible()
    historial.select_option(index=1); expect(syn).to_contain_text("Estás viendo una síntesis anterior"); historial.select_option(index=0)
    print("5 expediente por etapas; la síntesis se actualiza sola, propone preguntas y guarda su historial")
    dossier.screenshot(path=f"{SHOTS}/f6_2_sintesis.png")
    # 6. Beto (lectura, sin permiso sensible)
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 1000}); p2 = ctx2.new_page(); watch(p2, "B ")
    login(p2, "beto@demo.test"); open_person(p2, shared=True)
    s2 = p2.get_by_role("region", name="Evaluaciones posteriores")
    expect(s2.get_by_text("requiere un permiso adicional")).to_be_visible()
    expect(s2.get_by_role("list", name="Evaluaciones").get_by_role("listitem")).to_have_count(2)
    expect(s2.get_by_role("button", name="Registrar evaluación")).to_have_count(0)
    d2 = p2.get_by_role("region", name="Expediente por etapas")
    expect(d2.get_by_text("síntesis más reciente que incluye psicometría o fotografías del estudio")).to_be_visible()
    # Sí ve una síntesis anterior, generada sola antes de que hubiera psicometría o fotografías.
    s2 = d2.get_by_role("region", name="Síntesis"); expect(s2).to_be_visible()
    expect(s2).not_to_contain_text("psicométricas"); expect(s2).not_to_contain_text("fotografías del estudio")
    print("6 sin el permiso adicional no se ven psicometría, estudio ni las síntesis que los incluyen")
    # 6b. Analista de estudios: solo ve los estudios, de cualquier vacante
    ctxa = browser.new_context(viewport={"width": 1440, "height": 1000}); pa = ctxa.new_page()
    pa.on("pageerror", lambda e: errors.append("C " + str(e)))
    login(pa, "carla@demo.test")
    expect(pa.get_by_role("heading", name="Estudios socioeconómicos")).to_be_visible()
    expect(pa.get_by_role("link", name="Estudios", exact=True)).to_be_visible(); expect(pa.get_by_role("link", name="Vacantes", exact=True)).to_have_count(0)
    fila = pa.get_by_role("button", name="Abrir el estudio de Persona Ficticia 3"); expect(fila).to_contain_text("Estudio: En proceso")
    pa.screenshot(path=f"{SHOTS}/f6_3_analista.png", full_page=True)
    fila.click(); sa = pa.get_by_role("region", name="Evaluaciones posteriores")
    expect(sa.get_by_role("list", name="Evaluaciones").get_by_role("listitem")).to_have_count(1)
    sa.get_by_role("button", name="Registrar evaluación").click()
    expect(sa.get_by_label("Tipo de evaluación").locator("option")).to_have_count(2)
    # 6c. Referencias laborales y personales: las registra la analista y la IA las ordena
    sa.get_by_label("Tipo de evaluación").select_option("REFERENCIAS"); sa.get_by_role("button", name="Registrar", exact=True).click()
    sa.get_by_role("button", name="Agregar referencia").click()
    sa.get_by_label("Nombre de la referencia 1").fill("Jefa Ficticia Uno")
    sa.get_by_label("Empresa o relación con la persona 1").fill("Empresa Ficticia Uno")
    sa.get_by_label("Resultado del contacto 1").select_option("CONTACTADA")
    sa.get_by_label("Lo que dijo la referencia 1").fill("Confirma el puesto de analista de nómina y el periodo.")
    sa.get_by_label("Estado", exact=True).select_option("EN_PROCESO")
    sa.get_by_role("button", name="Guardar", exact=True).click()
    expect(sa.get_by_role("status").filter(has_text="Evaluación guardada")).to_be_visible()
    sa.get_by_role("button", name="Analizar con IA").click()
    resumen = sa.get_by_role("region", name="Resumen de la IA")
    expect(resumen).to_contain_text("Coincide con el CV"); expect(resumen).to_contain_text("no un hecho comprobado")
    pa.screenshot(path=f"{SHOTS}/f6_4_referencias.png", full_page=True)
    print("6c la analista registra referencias y la IA las ordena y contrasta con el CV")
    # 6d. Sin el formato en blanco cargado, la descarga explica qué falta
    sa.get_by_role("list", name="Evaluaciones").get_by_role("button", name=re.compile("Estudio socioeconómico")).click()
    descargar = sa.get_by_role("button", name="Descargar en el formato de la empresa (Excel)")
    descargar.click()
    expect(sa.get_by_role("alert").filter(has_text="Todavía no se ha cargado el formato en blanco")).to_be_visible()
    print("6d sin el formato en blanco, la descarga pide que un administrador lo suba")
    # 7. Admin: formularios (en otra ventana; la analista sigue en el estudio)
    ctx3 = browser.new_context(viewport={"width": 1440, "height": 1000}); p3 = ctx3.new_page(); watch(p3, "A ")
    login(p3, "admin@demo.test"); p3.get_by_role("link", name="Formularios", exact=True).click()
    p3.get_by_role("button", name="SGC.F3.RH. Estudio socioeconómico").click()
    expect(p3.get_by_text("Todavía no se ha cargado")).to_be_visible()
    p3.get_by_label("Formato en blanco del estudio (Excel)").set_input_files(EN_BLANCO)
    expect(p3.get_by_role("status").filter(has_text="Formato cargado")).to_be_visible()
    expect(p3.get_by_role("button", name="Sustituir el formato en blanco")).to_be_visible()
    p3.screenshot(path=f"{SHOTS}/f6_6_formato_en_blanco.png", full_page=True)
    print("7a el administrador sube el formato en blanco de la empresa")
    # 7b. La analista descarga el estudio en ese formato, con datos y fotografías
    with pa.expect_download() as d: descargar.click()
    assert d.value.suggested_filename.startswith("Estudio socioeconomico"), d.value.suggested_filename
    assert d.value.suggested_filename.endswith(".xlsx")
    hoja = load_workbook(io.BytesIO(Path(d.value.path()).read_bytes())).active
    textos = [str(c.value) for fila_ in hoja.iter_rows() for c in fila_ if c.value not in (None, "")]
    assert any(t.startswith("Nombre completo: ") and len(t) > 20 for t in textos), [t for t in textos if "Nombre" in t]
    assert len(hoja._images) == 3, len(hoja._images)  # el logotipo y las dos fotografías del estudio
    expect(sa.get_by_role("status").or_(sa.get_by_role("alert")).filter(has_text="ormato")).to_be_visible()
    print("7b la analista descarga el estudio en el formato de la empresa:", d.value.suggested_filename, "| imágenes:", len(hoja._images))
    pa.goto(BASE + "/vacantes"); expect(pa.get_by_role("alert").filter(has_text="solo da acceso a los estudios")).to_be_visible(); print("6b analista de estudios: ve su lista y el estudio; no ve otras evaluaciones ni las vacantes")
    # 7c. Admin: una versión nueva del formulario
    p3.get_by_role("button", name="Agregar campo").first.click()
    p3.get_by_label("Nombre del campo 2 de la sección 1", exact=True).fill("Medio de transporte declarado")
    p3.get_by_role("button", name="Guardar cambios").click()
    expect(p3.get_by_role("heading", name="SGC.F3.RH. Estudio socioeconómico · versión 2")).to_be_visible(); print("7 el administrador guarda una versión nueva del formulario")
    # 8. Móvil
    m = browser.new_context(viewport={"width": 390, "height": 844}); pm = m.new_page(); watch(pm, "M ")
    login(pm, "ana@demo.test"); pm.goto(BASE + "/vacantes"); pm.get_by_role("button", name="Abrir Analista de Nómina").click()
    pm.get_by_role("button", name="Candidatos y etapas").click(); pm.get_by_role("list", name="Candidatos").get_by_role("button", name="Persona Ficticia 3").click()
    expect(pm.get_by_role("region", name="Evaluaciones posteriores")).to_be_visible()
    pm.get_by_role("button", name="Estudio socioeconómico", exact=False).first.click()
    overflow = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"); assert overflow == 0, overflow; print("8 móvil: desbordamiento horizontal =", overflow)
    browser.close()
print("errores:", sorted(set(errors)))
