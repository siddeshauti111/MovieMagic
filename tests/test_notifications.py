from unittest.mock import Mock

from botocore.exceptions import ClientError

from app import create_app
from conftest import sign_in, submit
from services.notification_service import Notifications, recipient_key
from test_booking import booking_data


def test_private_sns_publish_payload_and_failure():
    notifier = Notifications({"APP_MODE": "aws", "PRIVATE_EMAIL": False, "TOPIC_ARN": "topic"})
    notifier.enabled = True
    notifier.client = Mock()
    ticket = dict(booking_data(), booking_id="MVM-id", movie_name="Midnight Circuit",
                  theater="Central", address="Pune", amount_paid=480)
    assert notifier.send(ticket) == "ACCEPTED"
    payload = notifier.client.publish.call_args.kwargs
    assert payload["MessageAttributes"]["recipient"]["StringValue"] == recipient_key(ticket["email"])
    assert "A1, A10" in payload["Message"]
    notifier.client.publish.side_effect = ClientError({"Error": {"Code": "InternalError"}}, "Publish")
    assert notifier.send(ticket) == "FAILED"


def test_failed_sns_keeps_ticket(app):
    notifier = Mock()
    notifier.send.return_value = "FAILED"
    configured = create_app(dict(app.config, NOTIFICATIONS=notifier))
    client = configured.test_client()
    sign_in(client)
    response = submit(client, "/tickets", booking_data())
    assert b"Email delivery could not be confirmed" in client.get(response.location).data
    assert b"Midnight Circuit" in client.get("/bookings").data
