"""Small HTML helpers for Streamlit rendering."""


def metric_card_html(title: str, value: str, border_color: str, value_style: str = "") -> str:
    return f"""<div class="metric-card" style="border-top:3px solid {border_color};">
        <div class="metric-title">{title}</div>
        <div class="metric-value" style="{value_style}">{value}</div>
    </div>"""
