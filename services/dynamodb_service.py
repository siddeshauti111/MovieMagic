import time

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from .database import BookingConflict, DuplicateEmail, SeatConflict, lock_id, timestamp


class DynamoDatabase:
    def __init__(self, config):
        service = boto3.resource("dynamodb", region_name=config["REGION"])
        self.users = service.Table(config["USERS_TABLE"])
        self.bookings = service.Table(config["BOOKINGS_TABLE"])
        self.client = service.meta.client

    def register(self, user):
        try:
            self.users.put_item(Item=user, ConditionExpression="attribute_not_exists(email)")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateEmail from error
            raise

    def user(self, email):
        return self.users.get_item(Key={"email": email}, ConsistentRead=True).get("Item")

    def record_login(self, email):
        self.users.update_item(Key={"email": email}, ConditionExpression="attribute_exists(email)",
                               UpdateExpression="SET last_login=:now ADD login_count :one",
                               ExpressionAttributeValues={":now": timestamp(), ":one": 1})

    def occupied(self, show, seats):
        if not seats:
            return []
        ids = {lock_id(show, seat): seat for seat in seats}
        table = self.bookings.name
        # The resource client serializes DynamoDB values itself.
        pending = {table: {"Keys": [{"booking_id": key} for key in ids],
                           "ConsistentRead": True, "ProjectionExpression": "booking_id"}}
        found = []
        for attempt in range(5):
            response = self.client.batch_get_item(RequestItems=pending)
            found.extend(ids[item["booking_id"]] for item in response["Responses"].get(table, []))
            pending = response.get("UnprocessedKeys", {})
            if not pending:
                return sorted(found)
            time.sleep(0.15 * 2 ** attempt)
        raise RuntimeError("DynamoDB could not read all seat locks.")

    def create_booking(self, booking, show):
        records = [booking] + [
            {"booking_id": lock_id(show, seat), "record_type": "SEAT_LOCK",
             "ticket_id": booking["booking_id"], "seat": seat}
            for seat in booking["seats"]
        ]
        operations = [{"Put": {"TableName": self.bookings.name, "Item": record,
                               "ConditionExpression": "attribute_not_exists(booking_id)"}}
                      for record in records]
        for attempt in range(4):
            try:
                self.client.transact_write_items(TransactItems=operations)
                return
            except ClientError as error:
                reasons = error.response.get("CancellationReasons", [])
                if reasons and reasons[0]["Code"] == "ConditionalCheckFailed":
                    raise BookingConflict from error
                if any(reason["Code"] == "ConditionalCheckFailed" for reason in reasons[1:]):
                    raise SeatConflict from error
                if any(reason["Code"] == "TransactionConflict" for reason in reasons) and attempt < 3:
                    time.sleep(0.08 * 2 ** attempt)
                    continue
                raise

    def set_notification(self, booking_id, status):
        self.bookings.update_item(Key={"booking_id": booking_id},
                                  ConditionExpression="attribute_exists(booking_id)",
                                  UpdateExpression="SET notification_status=:status",
                                  ExpressionAttributeValues={":status": status})

    def booking(self, booking_id):
        item = self.bookings.get_item(Key={"booking_id": booking_id}, ConsistentRead=True).get("Item")
        return item if item and item.get("record_type") == "BOOKING" else None

    def history(self, user_id):
        params = {"FilterExpression": Attr("record_type").eq("BOOKING") & Attr("booked_by").eq(user_id),
                  "ConsistentRead": True}
        result = []
        while True:
            page = self.bookings.scan(**params)
            result.extend(page["Items"])
            if not page.get("LastEvaluatedKey"):
                return result
            params["ExclusiveStartKey"] = page["LastEvaluatedKey"]
