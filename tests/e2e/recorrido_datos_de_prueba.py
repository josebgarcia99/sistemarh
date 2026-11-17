"""Datos de prueba: la vacante ficticia con personas en cada etapa se ve completa
en las pantallas (pasos, candidatos por etapa, expediente y lista de la analista).

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración con
``DEMO_SAMPLE_DATA=1`` (lo fija ``run.py`` para este recorrido).
"""

# ruff: noqa
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS

errors = []
NAME = "Analista de Nómina · DATOS DE PRUEBA"
def login(page, email):
    page.goto(BASE + "/login")
    page.get_by_role("textbox", name="Correo", exact=True).fill(email)
    page.get_by_role("textbox", name="Contraseña", exact=True).fill(PW)
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("button", name="Cerrar sesión")).to_be_visible()
def watch(page, tag=""):
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: errors.append(f"{tag}{r.status} {r.request.method} {r.url.split('?')[0][-40:]}") if r.status >= 400 and "health" not in r.url else None)
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1440, "height": 1000}); watch(page)
    login(page, "ana@demo.test")
    page.get_by_role("link", name="Vacantes", exact=True).click()
    page.get_by_role("button", name=f"Abrir {NAME}", exact=True).click()
    # 1. La guía: todo listo, sigue trabajar con los candidatos
    expect(page.get_by_role("button", name="Paso 3: Cargar y evaluar CV")).to_contain_text("11 CV evaluados")
    expect(page.get_by_role("button", name="Paso 4: Candidatos y etapas")).to_have_attribute("aria-current", "step")
    page.screenshot(path=f"{SHOTS}/dp1_vacante.png", full_page=True); print("1 la vacante de prueba aparece con sus pasos completos")
    # 2. Personas repartidas en las etapas
    page.get_by_role("button", name="Paso 4: Candidatos y etapas").click()
    people = page.get_by_role("list", name="Candidatos")
    for stage in ("Revisión local RH (3)", "Llamada telefónica (2)", "Pruebas psicométricas (1)", "Entrevista con gerente (1)", "Prueba técnica (1)", "Estudio socioeconómico (1)"):
        expect(page.get_by_role("button", name=stage)).to_be_visible()
    page.screenshot(path=f"{SHOTS}/dp2_candidatos.png", full_page=True); print("2 hay personas en cada etapa, de revisión de RH a estudio socioeconómico")
    # 3. El expediente de quien va más avanzada tiene de todo
    people.get_by_role("button", name="Mariana Ficticia Ortega").click()
    page.get_by_role("list", name="Llamadas").get_by_role("button").first.click()
    expect(page.get_by_role("group", name="Cobertura de la llamada").first).to_contain_text("de 100")
    evaluaciones = page.get_by_role("list", name="Evaluaciones")
    for kind in ("Prueba psicométrica", "Entrevista con gerente", "Prueba técnica", "Referencias laborales y personales", "Estudio socioeconómico"):
        expect(evaluaciones.get_by_role("button", name=kind).first).to_be_visible()
    # La psicometría validada trae su reporte, con lo que significa según el propio reporte
    evaluaciones.get_by_role("button", name="Prueba psicométrica").click()
    psico = page.get_by_role("region", name="Resumen de la IA")
    expect(psico).to_contain_text("Qué significa, según el reporte"); expect(psico).to_contain_text("Preguntas para la siguiente etapa")
    psico.screenshot(path=f"{SHOTS}/dp4_psicometria.png")
    evaluaciones.get_by_role("button", name="Prueba psicométrica").click()
    evaluaciones.get_by_role("button", name="Referencias laborales y personales").click()
    expect(page.get_by_role("region", name="Resumen de la IA")).to_contain_text("Sin confirmar")
    expect(page.get_by_text("Preguntas sugeridas para la siguiente etapa")).to_be_visible()
    sintesis = page.get_by_role("region", name="Síntesis")
    expect(sintesis).to_contain_text("Qué aportó cada etapa frente a las anteriores"); expect(sintesis).to_contain_text("Llamada: confirma el puesto y los años del CV")
    expect(sintesis).to_contain_text("Coincidencias entre fuentes")
    expect(page.get_by_role("region", name="Resumen de la IA")).to_contain_text("Ejemplo de los datos de prueba")
    page.screenshot(path=f"{SHOTS}/dp3_expediente.png", full_page=True); print("3 el expediente muestra llamada medida, evaluaciones, referencias y síntesis de ejemplo")
    # 4. La analista de estudios la encuentra en su lista
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}); sa = ctx.new_page(); watch(sa, "C ")
    login(sa, "carla@demo.test")
    row = sa.get_by_role("button", name="Abrir el estudio de Mariana Ficticia Ortega")
    expect(row).to_contain_text("En proceso"); expect(row).to_contain_text("Referencias: Completado"); print("4 la analista ve el estudio en proceso y las referencias completadas")
    # 5. Móvil
    m = browser.new_context(viewport={"width": 390, "height": 844}); pm = m.new_page()
    login(pm, "ana@demo.test"); pm.goto(BASE + "/vacantes"); pm.get_by_role("button", name=f"Abrir {NAME}", exact=True).click()
    pm.get_by_role("button", name="Paso 4: Candidatos y etapas").click(); expect(pm.get_by_role("list", name="Candidatos")).to_be_visible()
    overflow = pm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"); assert overflow == 0, overflow
    print("5 móvil sin desbordamiento:", overflow)
    browser.close()
print("errores:", sorted(set(errors)))
