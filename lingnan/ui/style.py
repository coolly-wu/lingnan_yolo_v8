"""Small stylesheet layer for Fluent status colors and legacy widgets."""

STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC";
    color: #1F1F1F;
}
QMainWindow, QWidget#homePage {
    background: #F7F9FC;
}
QSplitter::handle {
    background: transparent;
}
QLabel#severity_green {
    background: #DFF6DD;
    color: #107C10;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QLabel#severity_amber {
    background: #FFF4CE;
    color: #8A6A00;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QLabel#severity_red {
    background: #FDE7E9;
    color: #A80000;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
QStatusBar {
    background: #FFFFFF;
    color: #6B7280;
    border-top: 1px solid #E5EAF3;
}
"""
