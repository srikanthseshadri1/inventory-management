"""
Tests for restock order API endpoints.
"""
from datetime import datetime

import pytest

import main


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Restock orders live in server memory, so reset them around every test."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


class TestDemandForecastPricing:
    """Test the restock fields added to demand forecasts."""

    def test_demand_forecast_restock_field_types(self, client):
        """Test that every forecast has a unit cost and lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for forecast in response.json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0


class TestRestockOrderEndpoints:
    """Test suite for restock order endpoints."""

    def test_get_all_restock_orders_empty(self, client):
        """Test that there are no restock orders before any are submitted."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Test submitting a valid restock order."""
        response = client.post("/api/restock-orders", json={
            "budget": 10000,
            "items": [{"sku": "WDG-001", "quantity": 100}],
        })
        assert response.status_code == 201

        order = response.json()
        for field in ["id", "order_number", "items", "total_value", "budget",
                      "status", "submitted_date", "lead_time_days", "expected_delivery"]:
            assert field in order
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["items"][0]["name"] == "Industrial Widget Type A"

    def test_restock_order_total_value_calculation(self, client):
        """Test that the total uses the server's unit costs."""
        response = client.post("/api/restock-orders", json={
            "budget": 10000,
            "items": [
                {"sku": "WDG-001", "quantity": 100},  # 100 x 24.99
                {"sku": "GSK-203", "quantity": 40},   # 40 x 12.75
            ],
        })
        order = response.json()

        assert abs(order["items"][0]["line_total"] - 2499.0) < 0.01
        assert abs(order["items"][1]["line_total"] - 510.0) < 0.01
        assert abs(order["total_value"] - 3009.0) < 0.01

    def test_restock_order_lead_time_uses_slowest_item(self, client):
        """Test that order lead time is the longest item lead time."""
        response = client.post("/api/restock-orders", json={
            "budget": 10000,
            "items": [
                {"sku": "GSK-203", "quantity": 10},  # 5 days
                {"sku": "MTR-304", "quantity": 1},   # 21 days
            ],
        })
        order = response.json()
        assert order["lead_time_days"] == 21

        submitted = datetime.fromisoformat(order["submitted_date"])
        expected = datetime.fromisoformat(order["expected_delivery"])
        assert (expected - submitted).days == 21

    def test_get_restock_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        first = client.post("/api/restock-orders", json={
            "budget": 1000, "items": [{"sku": "FLT-405", "quantity": 10}],
        }).json()
        second = client.post("/api/restock-orders", json={
            "budget": 1000, "items": [{"sku": "GSK-203", "quantity": 10}],
        }).json()

        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        ids = [order["id"] for order in response.json()]
        assert ids == [second["id"], first["id"]]
        assert first["order_number"] != second["order_number"]

    def test_create_restock_order_over_budget(self, client):
        """Test that an order costing more than the budget is rejected."""
        response = client.post("/api/restock-orders", json={
            "budget": 100,
            "items": [{"sku": "MTR-304", "quantity": 1}],  # 445.00
        })
        assert response.status_code == 400
        assert "exceeds budget" in response.json()["detail"]
        assert client.get("/api/restock-orders").json() == []

    def test_create_restock_order_unknown_sku(self, client):
        """Test that a SKU outside the demand forecast is rejected."""
        response = client.post("/api/restock-orders", json={
            "budget": 1000,
            "items": [{"sku": "NOPE-999", "quantity": 1}],
        })
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]

    def test_create_restock_order_duplicate_sku(self, client):
        """Test that the same SKU twice in one order is rejected."""
        response = client.post("/api/restock-orders", json={
            "budget": 1000,
            "items": [{"sku": "GSK-203", "quantity": 1}, {"sku": "GSK-203", "quantity": 2}],
        })
        assert response.status_code == 400

    @pytest.mark.parametrize("payload", [
        {"budget": 1000, "items": []},
        {"budget": 1000, "items": [{"sku": "GSK-203", "quantity": 0}]},
        {"budget": -1, "items": [{"sku": "GSK-203", "quantity": 1}]},
    ])
    def test_create_restock_order_invalid_input(self, client, payload):
        """Test validation of empty orders, zero quantities and negative budgets."""
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 422
