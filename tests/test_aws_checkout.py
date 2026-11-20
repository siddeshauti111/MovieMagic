from unittest.mock import Mock

from app import create_app
from conftest import sign_in, submit
from services.notification_service import recipient_key
from test_booking import booking_data


def test_aws_checkout_writes_booking_and_publishes_confirmation(monkeypatch):
    region = "us-east-1"
    topic = f"arn:aws:sns:{region}:123456789012:MovieTicketNotifications"
    for name, value in {
        "APP_MODE": "aws",
        "FLASK_SECRET_KEY": "fake-test-secret" * 3,
        "FLASK_DEBUG": "0",
        "COOKIE_SECURE": "0",
        "AWS_REGION": region,
        "SNS_TOPIC_ARN": topic,
        "SNS_PRIVATE_EMAIL_ENABLED": "1",
        "DYNAMODB_USERS_TABLE": "MovieMagic_Users",
        "DYNAMODB_BOOKINGS_TABLE": "MovieMagic_Bookings",
    }.items():
        monkeypatch.setenv(name, value)

    users = Mock()
    bookings = Mock()
    bookings.name = "MovieMagic_Bookings"
    dynamodb = Mock()
    dynamodb.Table.side_effect = {"MovieMagic_Users": users, bookings.name: bookings}.__getitem__
    sns = Mock()
    sdk_calls = Mock()
    sdk_calls.attach_mock(dynamodb.meta.client, "dynamodb")
    sdk_calls.attach_mock(sns, "sns")
    resource = Mock(return_value=dynamodb)
    client_factory = Mock(return_value=sns)
    monkeypatch.setattr("boto3.resource", resource)
    monkeypatch.setattr("boto3.client", client_factory)

    users.get_item.side_effect = lambda **kwargs: {
        "Item": users.put_item.call_args.kwargs["Item"]
    }
    client = create_app({"TESTING": True}).test_client()
    assert sign_in(client).status_code == 303
    users.update_item.assert_called_once()

    data = booking_data()
    response = submit(client, "/tickets", data)
    assert response.status_code == 303
    booking_id = response.location.rsplit("/", 1)[-1]

    resource.assert_called_once_with("dynamodb", region_name=region)
    client_factory.assert_called_once_with("sns", region_name=region)
    assert [call[0] for call in sdk_calls.mock_calls] == [
        "dynamodb.transact_write_items", "sns.publish"
    ]
    writes = dynamodb.meta.client.transact_write_items.call_args.kwargs["TransactItems"]
    record, *locks = [write["Put"]["Item"] for write in writes]
    assert record["booking_id"] == booking_id
    assert record["amount_paid"] == 480
    assert [(lock["seat"], lock["ticket_id"]) for lock in locks] == [
        (seat, booking_id) for seat in data["seats"]
    ]
    publish = sns.publish.call_args.kwargs
    assert publish["TopicArn"] == topic
    assert booking_id in publish["Message"]
    assert publish["MessageAttributes"]["recipient"]["StringValue"] == recipient_key(data["email"])
    bookings.update_item.assert_called_once_with(
        Key={"booking_id": booking_id},
        ConditionExpression="attribute_exists(booking_id)",
        UpdateExpression="SET notification_status=:status",
        ExpressionAttributeValues={":status": "ACCEPTED"},
    )
