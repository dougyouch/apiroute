from apiroute.testing import graphql_response


def test_data():
    response = graphql_response(data={"viewer": {"login": "a"}})
    assert response.status_code == 200
    assert response.json() == {"data": {"viewer": {"login": "a"}}}


def test_errors_without_data_send_null_data():
    assert graphql_response(errors=[{"message": "nope"}]).json() == {
        "data": None,
        "errors": [{"message": "nope"}],
    }


def test_status_and_extensions():
    response = graphql_response(errors=[{"message": "bad"}], status=400, extensions={"cost": 1})
    assert response.status_code == 400
    assert response.json()["extensions"] == {"cost": 1}


def test_explicit_null_data():
    assert graphql_response(data=None).json() == {"data": None}
