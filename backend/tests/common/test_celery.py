from config.celery import ping


def test_celery_ping_task_runs_eagerly():
    assert ping.delay().get() == "pong"
