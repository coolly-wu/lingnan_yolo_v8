"""Markdown 导出测试"""

import pytest

MD = """# 标题

## 小节
- 项目一
- 项目二

| 列A | 列B |
| :--- | :--- |
| 1 | 2 |

普通段落。
"""


def test_export_markdown_writes_file(tmp_path):
    from lingnan.data.markdown_exporter import export_markdown
    out = export_markdown(MD, tmp_path / "x.md")
    assert out.exists()
    assert out.read_text(encoding="utf-8") == MD


def test_export_markdown_creates_parent(tmp_path):
    from lingnan.data.markdown_exporter import export_markdown
    out = export_markdown("# hi", tmp_path / "sub" / "y.md")
    assert out.exists()


def test_export_markdown_pdf(tmp_path):
    pytest.importorskip("reportlab")
    from lingnan.data.markdown_exporter import export_markdown_pdf
    out = export_markdown_pdf(MD, tmp_path / "x.pdf", title="测试")
    assert out.exists()
    assert out.stat().st_size > 0
