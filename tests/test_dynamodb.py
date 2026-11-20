import json
from types import SimpleNamespace
from unittest.mock import Mock

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError

from services.database import BookingConflict, SeatConflict
from services.dynamodb_service import DynamoDatabase


@pytest.fixture
def database(monkeypatch):
    resource = Mock()
    resource.Table.side_effect = lambda name: SimpleNamespace(name=name)
    monkeypatch.setattr("services.dynamodb_service.boto3.resource", lambda *args, **kwargs: resource)
    return DynamoDatabase({"REGION": "local-test", "USERS_TABLE": "MovieMagic_Users",
                           "BOOKINGS_TABLE": "MovieMagic_Bookings"})


def test_dynamo_transaction_request(database):
    ticket = {"booking_id": "MVM-id", "record_type": "BOOKING", "seats": ["A1", "B3"]}
    database.create_booking(ticket, "show")
    operations = database.client.transact_write_items.call_args.kwargs["TransactItems"]
    puts = [operation["Put"] for operation in operations]
    assert all(put["TableName"] == "MovieMagic_Bookings" for put in puts)
    assert all(put["ConditionExpression"] == "attribute_not_exists(booking_id)" for put in puts)
    assert [put["Item"]["booking_id"] for put in puts] == ["MVM-id", "LOCK#show#A1", "LOCK#show#B3"]


@pytest.mark.parametrize("row,error_class", [(0, BookingConflict), (1, SeatConflict)])
def test_dynamo_reports_conditional_failure(database, row, error_class):
    reasons = [{"Code": "None"}, {"Code": "None"}]
    reasons[row]["Code"] = "ConditionalCheckFailed"
    database.client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "TransactionCanceledException"}, "CancellationReasons": reasons},
        "TransactWriteItems",
    )
    with pytest.raises(error_class):
        database.create_booking({"booking_id": "MVM-id", "seats": ["A1"]}, "show")


def test_dynamo_seat_reads_retry_unprocessed_keys(database):
    pending = {"MovieMagic_Bookings": {"Keys": [{"booking_id": "LOCK#show#B3"}]}}
    database.client.batch_get_item.side_effect = [
        {"Responses": {"MovieMagic_Bookings": [{"booking_id": "LOCK#show#A1"}]},
         "UnprocessedKeys": pending},
        {"Responses": {}},
    ]
    assert database.occupied("show", ["A1", "B3"]) == ["A1"]
    assert database.client.batch_get_item.call_args.kwargs["RequestItems"] == pending


def test_boto3_serializes_applied_booking_and_lock_values(monkeypatch):
    resource = boto3.Session(aws_access_key_id="unused", aws_secret_access_key="unused").resource(
        "dynamodb", region_name="us-east-1"
    )
    monkeypatch.setattr("services.dynamodb_service.boto3.resource", lambda *args, **kwargs: resource)
    database = DynamoDatabase({"REGION": "us-east-1", "USERS_TABLE": "MovieMagic_Users",
                               "BOOKINGS_TABLE": "MovieMagic_Bookings"})
    observed = {}

    def capture(params, **kwargs):
        observed.update(json.loads(params["body"]))
        return AWSResponse(url=params["url"], status_code=200, headers={}, raw=None), {}

    database.client.meta.events.register("before-call.dynamodb.TransactWriteItems", capture)
    database.create_booking({"booking_id": "MVM-id", "record_type": "BOOKING",
                             "seats": ["A1"], "ticket_price": 240}, "show")
    writes = observed["TransactItems"]
    assert writes[0]["Put"]["Item"]["ticket_price"] == {"N": "240"}
    assert writes[1]["Put"]["Item"]["booking_id"] == {"S": "LOCK#show#A1"}
