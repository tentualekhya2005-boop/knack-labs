import pytest
from app.worker import celery_app


@pytest.fixture(autouse=True, scope="session")
def configure_celery_for_tests():
    """Ensure Celery runs in eager mode during automated tests so tasks execute immediately without external workers."""
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
