import pytest
from django.db import connection


@pytest.mark.django_db
def test_pgvector_extension_is_enabled():
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        row = cursor.fetchone()
    assert row is not None
    assert row[0] == "vector"
