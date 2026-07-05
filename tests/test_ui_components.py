from ui_components import metric_card_html


def test_metric_card_html_contains_title_value_and_color():
    html = metric_card_html("Composite Score", "64.0/100", "#f2ca50")

    assert "Composite Score" in html
    assert "64.0/100" in html
    assert "#f2ca50" in html
