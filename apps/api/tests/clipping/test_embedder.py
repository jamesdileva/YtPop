"""Real embedder smoke test — shape + normalization (model cached in S6)."""

import math

import pytest

from app.domain.clipping.service import Embedder


def test_encode_shape_and_normalized():
    vecs = Embedder().encode(["hello world", "gaming highlights"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    for v in vecs:
        assert math.sqrt(sum(x * x for x in v)) == pytest.approx(1.0)
