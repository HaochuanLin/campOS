"""Guard the sidebar control contrast contract against accidental CSS regressions."""

from pathlib import Path


def test_sidebar_form_controls_have_explicit_high_contrast_styles():
    source = Path("src/campos/app.py").read_text(encoding="utf-8")

    # The sidebar is dark; editable controls must use a light surface and dark text.
    required_rules = (
        "section[data-testid=\"stSidebar\"] [data-baseweb=\"select\"] > div",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stNumberInput\"] input",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stNumberInput\"] > div",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stNumberInput\"] button",
        "background: #f4faf6 !important",
        "color: #102b2b !important",
        "-webkit-text-fill-color: #102b2b !important",
        "background: #e4eee7 !important",
    )
    missing = [rule for rule in required_rules if rule not in source]
    assert not missing, f"Sidebar contrast styles are missing or changed: {missing}"
