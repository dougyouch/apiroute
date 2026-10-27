import pytest

from apiroute.graphql.snake_case import snake_case


@pytest.mark.parametrize(
    "name, expected",
    [("repoName", "repo_name"), ("userID", "user_id"), ("HTMLUrl", "html_url"), ("first", "first"),
     ("after2", "after2"), ("item2Id", "item2_id")],
)  # fmt: skip
def test_snake_case(name, expected):
    assert snake_case(name) == expected
