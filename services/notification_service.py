import hashlib
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

STATUS = {
    "PENDING": "Email delivery could not be confirmed.",
    "SIMULATED": "Confirmation simulated locally.",
    "DISABLED": "Email notifications are disabled for this deployment.",
    "ACCEPTED": "Confirmation accepted by SNS. Delivery is unverified.",
    "FAILED": "Booking confirmed. Email delivery could not be confirmed.",
}


def recipient_key(email):
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


class Notifications:
    def __init__(self, config):
        self.local = config["APP_MODE"] == "local"
        self.enabled = config["PRIVATE_EMAIL"]
        self.arn = config["TOPIC_ARN"]
        self.client = None
        if not self.local and self.enabled:
            self.client = boto3.client("sns", region_name=config["REGION"])

    def send(self, ticket):
        booking_id = ticket["booking_id"]
        if self.local:
            return "SIMULATED"
        if not self.enabled:
            return "DISABLED"
        message = "\n".join([
            f"Hello {ticket['customer_name']},", "",
            "Your movie ticket booking has been confirmed.", "", "Booking details:",
            f"Booking ID: {booking_id}", f"Movie: {ticket['movie_name']}",
            f"Date: {ticket['show_date']}", f"Time: {ticket['show_time']}",
            f"Theater: {ticket['theater']}", f"Address: {ticket['address']}",
            f"Seat numbers: {', '.join(ticket['seats'])}",
            f"Amount paid: ₹{ticket['amount_paid']}", "", "Thank you for choosing MovieMagic!",
        ])
        try:
            self.client.publish(
                TopicArn=self.arn, Subject=f"MovieMagic Booking Confirmation - {booking_id}",
                Message=message,
                MessageAttributes={"recipient": {"DataType": "String",
                                                 "StringValue": recipient_key(ticket["email"])}},
            )
        except (BotoCoreError, ClientError):
            logger.warning("SNS publish failed for booking %s", booking_id)
            return "FAILED"
        return "ACCEPTED"
