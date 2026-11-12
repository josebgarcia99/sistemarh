"""Ayudas de IA: llenar el perfil desde un documento y proponer mejoras a los criterios.

Se ejecuta con ``python tests/e2e/run.py``, sobre el modo demostración.
"""

# ruff: noqa
import os
from playwright.sync_api import sync_playwright, expect
from comun import BASE, PW, SHOTS
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: errors.append(f"{r.status} {r.request.method} {r.url.split('?')[0][-50:]}") if r.status >= 400 and "health" not in r.url else None)
    page.goto(BASE + "/login")
    page.get_by_role("textbox", name="Correo", exact=True).fill("ana@demo.test")
    page.get_by_role("textbox", name="Contraseña", exact=True).fill(PW)
    page.get_by_role("button", name="Entrar").click()
    page.get_by_role("link", name="Vacantes", exact=True).click()
    page.get_by_role("button", name="Abrir Auxiliar Contable").click()
    page.get_by_role("button", name="Perfil, prompt y evaluación de CV").click()
    expect(page.get_by_text("Todavía no hay perfil")).to_be_visible()
    page.get_by_role("button", name="Llenar con IA desde un documento").click()
    page.get_by_label("Documento de la vacante").select_option(label="Perfil Auxiliar Contable.docx")
    page.get_by_role("button", name="Leer con IA").click()
    expect(page.get_by_role("status").filter(has_text="todavía no se ha guardado")).to_be_visible()
    expect(page.get_by_label("Objetivo del puesto")).to_have_value("Registrar las operaciones contables del mes (respuesta simulada).")
    expect(page.get_by_text("Todavía no hay perfil")).to_be_visible(); print("1 la IA llena el formulario desde el documento y no guarda nada")
    page.screenshot(path=f"{SHOTS}/ia1_perfil.png", full_page=True)
    page.get_by_role("button", name="Cerrar", exact=True).click()
    page.get_by_role("button", name="Guardar perfil").click()
    expect(page.get_by_role("status").filter(has_text="versión 1")).to_be_visible(); print("2 la persona lo guarda como versión 1")
    page.get_by_role("button", name="Prompt de evaluación").click()
    page.get_by_role("button", name="Generar borrador desde el perfil").click()
    expect(page.get_by_role("list", name="Criterios").get_by_role("listitem")).to_have_count(3)
    page.get_by_role("button", name="Proponer mejoras con IA").click()
    panel = page.get_by_role("region", name="Mejoras propuestas por la IA")
    expect(panel.get_by_role("button", name="Aplicar a C1")).to_be_visible()
    expect(panel.get_by_text("Propuesta simulada")).to_be_visible(); print("3 la IA propone redacción para los 3 criterios, con sus avisos")
    page.screenshot(path=f"{SHOTS}/ia2_criterios.png", full_page=True)
    panel.get_by_role("button", name="Aplicar todas").click()
    expect(page.get_by_role("list", name="Criterios").get_by_role("listitem")).to_have_count(3)
    page.get_by_role("button", name="Guardar cambios").click()
    expect(page.get_by_role("status").filter(has_text="Cambios guardados")).to_be_visible()
    expect(page.get_by_label("Descripción del criterio C1")).to_have_value("Redacción simulada: busca en el CV evidencia con fechas."); print("4 al aplicar y guardar, siguen siendo 3 criterios con la nueva redacción")
    page.get_by_role("button", name="Perfil de puesto").click()
    page.get_by_role("button", name="Llenar con IA desde un documento").click()
    page.get_by_label("Texto del perfil").fill("corto")
    page.get_by_role("button", name="Leer con IA").click()
    expect(page.get_by_role("alert").filter(has_text="muy corto")).to_be_visible(); print("5 un texto demasiado corto se rechaza con su motivo")
    browser.close()
print("errores:", sorted(set(errors)))
