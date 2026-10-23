from apiroute.codegen.plain_text import plain_text


def test_html_becomes_plain_text():
    text = (
        "Gets an item.<br><br>The <code>sku</code> is <strong>required</strong>."
        "<ul><li>One</li><li>Two &amp; three</li></ul><p>Done.</p>"
    )
    assert plain_text(text) == "Gets an item.\n\nThe sku is required.\n- One\n- Two & three\nDone."


def test_plain_text_is_left_alone():
    assert plain_text("  Just text, 2 < 3 isn't a tag  ") == "Just text, 2 < 3 isn't a tag"
    assert plain_text("") == ""
