from apiroute.path_template import PathTemplate


def render(path, **values):
    return PathTemplate(path).render(values.__getitem__, str)


def test_names_in_order_without_duplicates():
    assert PathTemplate("/a/{x}/b/:y/{x}").names == ("x", "y")


def test_renders_brace_and_colon_parameters():
    assert render("/users/{id}/repos/:repo", id=1, repo="api") == "/users/1/repos/api"


def test_colon_after_a_word_character_is_literal():
    template = PathTemplate("/v1/items:batchGet/{name}:cancel/slots/12:30")
    assert template.names == ("name",)
    assert template.render(lambda name: "op", str) == "/v1/items:batchGet/op:cancel/slots/12:30"


def test_values_go_through_escape():
    template = PathTemplate("/files/{name}")
    assert template.render(lambda name: "a/b", lambda value: value.upper()) == "/files/A/B"
