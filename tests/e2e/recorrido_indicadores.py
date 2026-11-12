"""Cierre e indicadores: resultado final, reapertura, tablero, histórico, Excel y permisos.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración.
"""

# ruff: noqa
import io, os
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS
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
def candidates(page):
    page.get_by_role("link", name="Vacantes", exact=True).click()
    page.get_by_role("button", name="Abrir Analista de Nómina").click()
    page.get_by_role("button", name="Candidatos y etapas").click()
def tile(region, label):
    return region.locator("div", has=region.page.get_by_text(label, exact=True)).last.locator("dd").first
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1440, "height": 1000}); watch(page)
    login(page, "ana@demo.test")
    # 1. Inicio antes de empezar
    today = page.get_by_role("region", name="Hoy")
    expect(tile(today, "Vacantes propias")).to_have_text("2"); expect(tile(today, "Procesos pendientes")).to_have_text("0")
    print("1 inicio: tablero propio con 2 vacantes y nada en proceso")
    # 2. Evaluar los CV
    page.get_by_role("link", name="Vacantes", exact=True).click(); page.get_by_role("button", name="Abrir Analista de Nómina").click()
    page.get_by_role("button", name="Perfil, prompt y evaluación de CV").click(); page.get_by_role("button", name="Evaluación de CV").click()
    page.get_by_role("button", name="Evaluar 4 CV").click(); expect(page.get_by_role("status").filter(has_text="terminó")).to_be_visible()
    page.get_by_role("button", name="Volver a vacantes").click()
    # 3. Contratación
    candidates(page)
    expect(page.get_by_text("Plazas cubiertas: 0 de")).to_be_visible()
    people = page.get_by_role("list", name="Candidatos")
    names = [b.inner_text() for b in people.get_by_role("button").all() if "Persona" in b.inner_text()]
    people.get_by_role("button", name=names[0]).click()
    page.get_by_role("button", name="Mover de etapa").click()
    dialog = page.get_by_role("dialog"); dialog.get_by_label("Etapa de destino").select_option(label="3. Llamada telefónica")
    dialog.get_by_label("Motivo").fill("Avanza por decisión de RH"); dialog.get_by_role("button", name="Mover").click()
    expect(page.get_by_role("status").filter(has_text="Etapa actualizada")).to_be_visible()
    page.get_by_role("button", name="Registrar resultado final").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Resultado").select_option("NO_CONTRATADO"); expect(dialog.get_by_label("Fecha de incorporación (opcional)")).to_have_count(0)
    dialog.get_by_role("button", name="Registrar resultado").click(); expect(dialog.get_by_role("alert")).to_contain_text("motivo")
    dialog.get_by_label("Resultado").select_option("CONTRATADO"); dialog.get_by_label("Fecha de incorporación (opcional)").fill("2026-12-01")
    dialog.get_by_label("Observaciones (opcional)").fill("Acepta la oferta.")
    dialog.get_by_role("button", name="Registrar resultado").click()
    expect(page.get_by_role("status").filter(has_text="Resultado final registrado")).to_be_visible()
    result = page.get_by_role("region", name="Resultado final")
    expect(result).to_contain_text("Contratado"); expect(result).to_contain_text("Fecha de incorporación: 1 dic 2026"); expect(result).to_contain_text("Ana Demo")
    expect(page.get_by_role("button", name="Mover de etapa")).to_have_count(0)
    expect(page.get_by_role("list", name="Historial de movimientos").get_by_role("listitem").first).to_contain_text("Contratación")
    page.screenshot(path=f"{SHOTS}/f7_resultado_final.png", full_page=True)
    print(f"2 contratación de {names[0]}: queda con fecha de incorporación, responsable e historial; ya no se mueve")
    # 4. Desistimiento y reapertura
    page.get_by_role("button", name="Volver a candidatos").click()
    expect(page.get_by_text("Plazas cubiertas: 1 de")).to_be_visible()
    people.get_by_role("button", name=names[1]).click()
    page.get_by_role("button", name="Registrar resultado final").click()
    dialog = page.get_by_role("dialog"); dialog.get_by_label("Resultado").select_option("DESISTIO"); dialog.get_by_label("Motivo", exact=True).fill("Aceptó otra oferta")
    dialog.get_by_role("button", name="Registrar resultado").click()
    expect(page.get_by_role("region", name="Resultado final")).to_contain_text("Desistió")
    page.get_by_role("button", name="Reabrir proceso").click()
    dialog = page.get_by_role("dialog"); dialog.get_by_label("Motivo").fill("Volvió a estar interesada"); dialog.get_by_role("button", name="Confirmar").click()
    expect(page.get_by_role("status").filter(has_text="Proceso reabierto")).to_be_visible()
    expect(page.get_by_role("list", name="Resultados anulados")).to_contain_text("Volvió a estar interesada")
    page.get_by_role("button", name="Registrar resultado final").click()
    dialog = page.get_by_role("dialog"); dialog.get_by_label("Resultado").select_option("DESISTIO"); dialog.get_by_label("Motivo", exact=True).fill("Aceptó otra oferta")
    dialog.get_by_role("button", name="Registrar resultado").click(); expect(page.get_by_role("region", name="Resultado final")).to_contain_text("Aceptó otra oferta")
    print("3 desistimiento, reapertura (el anterior queda anulado, no borrado) y nuevo cierre")
    # 5. Inicio con cifras
    page.get_by_role("link", name="Inicio", exact=True).click()
    today = page.get_by_role("region", name="Hoy"); period = page.get_by_role("region", name="Últimos 30 días")
    expect(tile(period, "CV analizados")).to_have_text("4"); expect(tile(period, "Contrataciones")).to_have_text("1"); expect(tile(period, "Procesos cerrados")).to_have_text("2")
    expect(tile(today, "Procesos pendientes")).to_have_text("2")
    expect(page.get_by_role("list", name="Actividad reciente").get_by_role("listitem").first).to_contain_text("Desistimiento")
    page.screenshot(path=f"{SHOTS}/f7_inicio.png", full_page=True)
    print("4 inicio: 4 CV analizados, 2 procesos cerrados, 1 contratación, 2 pendientes y actividad reciente")
    # 6. Indicadores
    page.get_by_role("link", name="Ver indicadores y reportes").click()
    expect(page.get_by_role("list", name="Embudo por etapa").get_by_role("listitem").last).to_have_text("Contratadas1")
    rows = page.get_by_role("table", name="Vacantes").get_by_role("row")
    expect(rows.filter(has_text="Analista de Nómina")).to_contain_text("1 de")
    expect(page.get_by_role("region", name="Reclutadores")).to_have_count(0); expect(page.get_by_role("region", name="Uso de IA")).to_have_count(0)
    page.screenshot(path=f"{SHOTS}/f7_indicadores.png", full_page=True)
    print("5 indicadores de Ana: embudo, tiempos, vacantes y mensual; sin datos reservados al administrador")
    # 7. Histórico y Excel
    page.get_by_role("button", name="Histórico de candidatos").click()
    expect(page.get_by_text("4 postulaciones")).to_be_visible()
    page.get_by_role("form", name="Filtros").get_by_label("Resultado final").select_option("CONTRATADO"); page.get_by_role("button", name="Aplicar filtros").click()
    expect(page.get_by_text("1 postulación", exact=True)).to_be_visible()
    row = page.get_by_role("table", name="Postulaciones").get_by_role("row").nth(1)
    expect(row).to_contain_text(names[0]); expect(row).to_contain_text("Entra el 1 dic 2026")
    page.screenshot(path=f"{SHOTS}/f7_historico.png", full_page=True)
    page.get_by_role("button", name="Descargar en Excel").click()
    link = page.get_by_role("link", name="Descargar Postulaciones_")
    expect(link).to_be_visible()
    content = page.request.get(BASE + link.get_attribute("href")).body()
    sheet = load_workbook(io.BytesIO(content))["Postulaciones"]
    assert sheet.max_row == 2 and sheet["A2"].value == names[0] and sheet["F2"].value == "Contratado", sheet["F2"].value
    page.get_by_role("button", name="Reportes generados").click()
    item = page.get_by_role("list", name="Reportes").get_by_role("listitem").first
    expect(item).to_contain_text("1 postulación"); expect(item).to_contain_text("Resultado final: Contratado"); expect(item).to_contain_text("SHA-256")
    page.screenshot(path=f"{SHOTS}/f7_reportes.png", full_page=True)
    print("6 histórico filtrado por resultado, Excel descargado y abierto (1 fila, Contratado), y registro con huella")
    # 8. Administrador
    page.get_by_role("button", name="Cerrar sesión").click(); page.wait_for_url("**/login*"); login(page, "admin@demo.test")
    page.get_by_role("link", name="Indicadores", exact=True).click()
    people = page.get_by_role("table", name="Reclutadores")
    expect(people.get_by_role("row").filter(has_text="Ana Demo")).to_be_visible()
    usage = page.get_by_role("region", name="Uso de IA"); expect(usage).to_contain_text("Evaluación de CV")
    page.screenshot(path=f"{SHOTS}/f7_indicadores_admin.png", full_page=True)
    page.get_by_role("button", name="Descargar en Excel").click()
    link = page.get_by_role("link", name="Descargar Indicadores_"); expect(link).to_be_visible()
    book = load_workbook(io.BytesIO(page.request.get(BASE + link.get_attribute("href")).body()))
    assert book.sheetnames == ["Resumen", "Etapas", "Vacantes", "Reclutadores", "Mensual", "IA"], book.sheetnames
    print("7 administrador: carga por responsable, uso de IA y Excel de indicadores con 6 hojas")
    # 9. Beto: solo lo compartido
    page.get_by_role("button", name="Cerrar sesión").click(); page.wait_for_url("**/login*"); login(page, "beto@demo.test")
    today = page.get_by_role("region", name="Hoy")
    own = tile(today, "Vacantes propias").inner_text(); shared = tile(today, "Vacantes compartidas").inner_text()
    print(f"8 Beto: propias {own}, compartidas {shared}")
    # 10. Móvil
    mobile = browser.new_page(viewport={"width": 390, "height": 800}); login(mobile, "admin@demo.test")
    for path in ("/", "/indicadores"):
        mobile.goto(BASE + path); expect(mobile.get_by_role("region", name="Hoy")).to_be_visible()
        overflow = mobile.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, (path, overflow)
    mobile.screenshot(path=f"{SHOTS}/f7_movil.png", full_page=True)
    print("9 móvil: inicio e indicadores sin desbordamiento horizontal")
    browser.close()
print("ERRORES:", errors if errors else "ninguno")
