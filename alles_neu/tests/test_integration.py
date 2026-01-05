def _login_admin(client):
    resp = client.post(
        "/login",
        data={"mode": "admin", "password": "admin123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("role") == "admin"
        assert sess.get("is_logged_in") is True
    return resp


def _login_station(client, app):
    # hole einen gültigen PIN aus der DB
    with app.app_context():
        from app import get_db

        db = get_db()
        pin = db.ensure_default_station_pin(

            station=app.config.get("STATION_DEFAULT_NAME", "Station"),
            max_logins=app.config.get("STATION_DEFAULT_MAX_LOGINS", 1),
            length=app.config.get("STATION_DEFAULT_PIN_LENGTH", 6),
        )
    resp = client.post(
        "/login",
        data={"mode": "station", "password": pin, "discipline": "Sprinten"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("role") == "station"
        assert sess.get("is_logged_in") is True
        assert sess.get("discipline") == "Sprinten"
    return pin


def test_station_login_and_get_riege_flow(client, app):
    _login_station(client, app)

    # hole einen Riegenführer
    with app.app_context():
        from app import get_db

        db = get_db()
        riegen = db.get_riegenfuehrer()

        assert len(riegen) >= 1
        riegen_id = riegen[0][0]

    resp = client.post("/get_riege", json={"riegenfuehrer_id": riegen_id})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status_list" in data
    assert "progress" in data
    # Progress-Totals passen zur Seed-Logik (>=1 Schüler)
    assert data["progress"]["total"] >= 1


def test_admin_login_and_disziplin_crud_flow(client):
    _login_admin(client)

    # create

    create_resp = client.post(
        "/admin/disziplinen/create",
        json={
            "name": "IntegrationTest",
            "display_name": "Integration Test",
            "result_format": "distance",
            "num_rounds": 2,
            "unit": "m",
            "description": "Integrationstest-Disziplin",
            "sort_order": 99,
        },
    )
    assert create_resp.status_code == 200
    create_data = create_resp.get_json()
    disziplin_id = create_data.get("id")
    assert disziplin_id is not None

    # list contains
    list_resp = client.get("/admin/disziplinen/list")
    assert list_resp.status_code == 200
    disziplinen = list_resp.get_json().get("disziplinen", [])
    assert any(d["id"] == disziplin_id for d in disziplinen)

    # update
    update_resp = client.put(
        f"/admin/disziplinen/{disziplin_id}",
        json={"unit": "cm", "num_rounds": 3},
    )
    assert update_resp.status_code == 200
    update_data = update_resp.get_json()
    assert "aktualisiert" in update_data.get("message", "").lower()

    # verify update via get
    get_resp = client.get(f"/admin/disziplinen/{disziplin_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.get_json()
    assert get_data["unit"] == "cm"
    assert get_data["num_rounds"] == 3

    # delete
    delete_resp = client.delete(f"/admin/disziplinen/{disziplin_id}")
    assert delete_resp.status_code == 200

    # ensure removed
    list_resp_after = client.get("/admin/disziplinen/list")
    disziplinen_after = list_resp_after.get_json().get("disziplinen", [])
    assert all(d["id"] != disziplin_id for d in disziplinen_after)
