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
        "background: #d6e5da !important",
        "[data-testid=\"stNumberInput\"] button svg",
        "stroke: #102b2b !important",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stSelectbox\"] svg",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stMultiSelect\"] svg",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stMultiSelect\"] svg path",
        "section[data-testid=\"stSidebar\"] [data-testid=\"stMultiSelect\"] button",
        "border-color: #9bb5a5 !important",
        "opacity: 1 !important",
    )
    missing = [rule for rule in required_rules if rule not in source]
    assert not missing, f"Sidebar contrast styles are missing or changed: {missing}"


def test_custom_site_ui_discloses_calibration_and_water_savings_limits():
    source = Path("src/campos/app.py").read_text(encoding="utf-8")

    required_disclosures = (
        "a surveyed polygon/layout does not calibrate sprinkler physics",
        "A radial-profile CSV describes relative spray shape only",
        "it does not provide absolute flow",
        "wind, drift, network pressure losses, and field accuracy remain unvalidated",
        "campOS does not claim litres saved or payback",
    )
    missing = [disclosure for disclosure in required_disclosures if disclosure not in source]
    assert not missing, f"Custom-site calibration disclosures are missing or changed: {missing}"
