from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_evaluation_query_docs_script_runs() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_evaluation_query_docs.py")],
        cwd=ROOT,
        check=True,
    )
    md = (ROOT / "docs" / "evaluation_queries_and_labels.md").read_text(encoding="utf-8")
    assert "## Table of contents" in md
    assert '[Text queries](#text-queries)' in md
    assert '[Image queries](#image-queries)' in md
    assert '[Image + text queries](#image-text-queries)' in md
    assert '<a id="text-queries"></a>' in md
    assert "eval_query_images/" in md
    imgs = list((ROOT / "docs" / "eval_query_images").glob("*"))
    assert len(imgs) >= 10
