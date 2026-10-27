from apiroute.codegen.generated_header import MARKER, generated_header


def test_one_line_when_it_fits():
    header = generated_header("1.9.0", "shop.yaml")
    assert header == f"{MARKER} 1.9.0 from shop.yaml. Do not edit: regenerate instead."


def test_do_not_edit_moves_to_its_own_line_when_long():
    header = generated_header("1.9.0", "github_schema.graphql and github_operations_directory")
    first, second = header.split("\n")
    assert first == f"{MARKER} 1.9.0 from github_schema.graphql and github_operations_directory."
    assert second == "# Do not edit: regenerate instead."
    assert all(len(line) <= 100 for line in header.split("\n"))
