import pytest

from ml.content_based.index import ContentSimilarityIndex


@pytest.fixture(autouse=True)
def reset_content_index():
    ContentSimilarityIndex.invalidate()
    yield
    ContentSimilarityIndex.invalidate()
