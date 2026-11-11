from __future__ import annotations

from worker.celery_app import create_celery_app
from worker.jobs.system import ping

from app.core.config.settings import Environment, Settings


def _app():
    settings = Settings(environment=Environment.TEST, redis_url="redis://localhost:6379/0")
    return create_celery_app(settings)


def test_los_mensajes_solo_admiten_json():
    conf = _app().conf
    assert conf.task_serializer == "json"
    assert conf.accept_content == ["json"]


def test_no_hay_backend_de_resultados_el_estado_vive_en_sql_server():
    conf = _app().conf
    assert conf.result_backend is None
    assert conf.task_ignore_result is True


def test_las_tareas_se_confirman_al_terminar():
    conf = _app().conf
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1


def test_la_tarea_ping_esta_registrada_y_responde():
    app = _app()
    app.loader.import_default_modules()
    assert "system.ping" in app.tasks
    assert ping.apply().get() == {"status": "ok"}
