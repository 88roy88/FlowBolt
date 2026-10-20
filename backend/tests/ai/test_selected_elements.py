from flow44.ai.selected_elements import MAX_SELECTED_ELEMENTS, format_selected_elements, parse_selected_elements

BUTTON = {
    "tag": "button",
    "selector": "main > button.cta",
    "text": "Sign up",
    "classes": "cta px-4",
    "html": '<button class="cta px-4">Sign up</button>',
    "components": ["PricingCard", "App"],
}


def test_parse_keeps_valid_elements() -> None:
    [el] = parse_selected_elements([BUTTON])
    assert el.tag == "button"
    assert el.components == ["PricingCard", "App"]


def test_parse_drops_invalid_items_and_non_lists() -> None:
    assert parse_selected_elements(None) == []
    assert parse_selected_elements({"tag": "div"}) == []
    assert parse_selected_elements(["nope", {"tag": ""}, {"selector": "x"}]) == []


def test_parse_caps_count_and_lengths() -> None:
    raw = [{**BUTTON, "html": "x" * 5000, "components": ["A", "B", "C", "D", "E", 3]}] * 10
    elements = parse_selected_elements(raw)
    assert len(elements) == MAX_SELECTED_ELEMENTS
    assert len(elements[0].html) == 600
    assert elements[0].components == ["A", "B", "C", "D"]


def test_format_lists_each_element() -> None:
    block = format_selected_elements(parse_selected_elements([BUTTON, {"tag": "div"}]))
    assert block.startswith("<selected_elements>")
    assert block.endswith("</selected_elements>")
    assert "1. <button> in components: PricingCard < App" in block
    assert "   selector: main > button.cta" in block
    assert '   text: "Sign up"' in block
    assert "2. <div>" in block
