"""Evaluaciones posteriores: prueba técnica, entrevista, psicometría, estudio, síntesis y datos sensibles.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración.
"""

# ruff: noqa
import os, re, tempfile
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS
# Fotografía inventada (un rectángulo de color) para adjuntarla al estudio.
FOTO = os.path.join(tempfile.mkdtemp(prefix="reclu-foto-"), "localizacion.jpg"); Image.new("RGB", (800, 600), (120, 150, 180)).save(FOTO)
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
    page.get_by_role("button", name="Perfil, prompt y evaluación de CV").click(); page.get_by_role("button", name="Evaluación de CV").click()
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
    sec.get_by_role("button", name="Resumir con IA").last.click()
    expect(sec.get_by_role("region", name="Resumen de la IA").last).to_contain_text("Resultado simulado"); print("3 psicometría: validar exige al profesional; la IA resume el documento cifrado")
    # 4. Estudio socioeconómico con digitalización
    sec.get_by_role("button", name="Registrar evaluación").click()
    sec.get_by_label("Tipo de evaluación").select_option("ESTUDIO_SOCIOECONOMICO")
    sec.get_by_role("button", name="Registrar", exact=True).click()
    sec.get_by_label("Formulario escaneado", exact=True).first.select_option(label="Estudio escaneado ficticio.docx")
    sec.get_by_role("button", name="Leer el formulario escaneado con IA").click()
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
    sec.get_by_label("Estado", exact=True).last.select_option("EN_PROCESO")
    sec.get_by_role("button", name="Guardar", exact=True).last.click()
    expect(sec.get_by_role("status").filter(has_text="Evaluación guardada")).to_be_visible(); print("4 estudio: la IA llena campos sin verificar; la persona marca lo verificado")
    page.screenshot(path=f"{SHOTS}/f6_1_evaluaciones.png", full_page=True)
    # 5. Expediente por etapas y síntesis
    dossier = page.get_by_role("region", name="Expediente por etapas")
    expect(dossier.get_by_text("Prueba técnica: Realizada")).to_be_visible()
    dossier.get_by_role("button", name="Generar síntesis").click()
    syn = dossier.get_by_role("region", name="Síntesis")
    expect(syn).to_contain_text("Hechos documentados"); expect(syn).to_contain_text("pruebas psicométricas validadas"); print("5 expediente por etapas con sus fuentes y síntesis por tipo de fuente")
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
    expect(d2.get_by_role("region", name="Síntesis")).to_have_count(0); print("6 sin el permiso adicional no se ven psicometría, estudio ni la síntesis que los incluye")
    # 7. Admin: formularios
    ctx3 = browser.new_context(viewport={"width": 1440, "height": 1000}); p3 = ctx3.new_page(); watch(p3, "A ")
    login(p3, "admin@demo.test"); p3.get_by_role("link", name="Formularios", exact=True).click()
    p3.get_by_role("button", name="SGC.F3.RH. Estudio socioeconómico").click()
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
