# AWS setup

## Open the lab

Open the AWS console and select a region available to your account for EC2, DynamoDB and SNS. If you are using a temporary lab, record its expiration time. This guide uses console steps. The application uses EC2 role credentials through Boto3.

## Create the DynamoDB tables

In DynamoDB, choose **Tables → Create table** twice. Choose a string partition key and leave the sort key blank.

| Table name | Partition key | Table class | Capacity |
| --- | --- | --- | --- |
| `MovieMagic_Users` | `email` | Standard | On-demand |
| `MovieMagic_Bookings` | `booking_id` | Standard | On-demand |

Leave secondary indexes empty and wait for both tables to become Active. Other attributes are populated by Flask.

If the lab requires provisioned capacity, size the bookings table for an 80-seat availability check using strongly consistent reads and for transactional writes. A two-seat booking writes three items and consumes at least six write capacity units before updating the notification status. Check for throttling during the live acceptance run if the lab mandates fixed 5/5 capacity. [DynamoDB capacity consumption](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html)

## Create and verify the SNS topic

1. In SNS, choose **Topics → Create topic**. Select **Standard**, name it `MovieTicketNotifications`, and record its ARN.
2. Create an **Email** subscription for each authorized test inbox. Open each inbox and click **Confirm subscription** in the SNS email.
3. Compute the recipient value using the exact normalized login email. On a machine with Python, run:

   ```bash
   python -c "import hashlib; print(hashlib.sha256(input('Subscriber email: ').strip().lower().encode('utf-8')).hexdigest())"
   ```

4. In **Subscriptions**, open each confirmed subscription and choose **Edit → Subscription filter policy**. Select **Message attributes** and save:

   ```json
   {"recipient":["REPLACE_WITH_THIS_SUBSCRIBERS_64_CHARACTER_HASH"]}
   ```

5. Wait up to 15 minutes for the policies to propagate. Audit every subscription, including other protocols, and keep publishing disabled while adding or changing subscriptions. An unfiltered subscription receives every message. Test with nonprivate payloads and two authorized inboxes. Publish a different test message for each recipient attribute and verify only the intended inbox receives it. Then set `SNS_PRIVATE_EMAIL_ENABLED=1` and restart Flask. If filtering is unavailable, keep the setting at `0` unless the entire topic is isolated to authorized test recipients using synthetic booking details. Review subscriptions before enabling any detailed publish. [AWS filter policies and propagation](https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html)
6. Register with the exact email address used to calculate the filter. SNS acceptance means accepted for processing. Verify actual receipt in the test inbox. Confirmation uses standard SNS and the inbox confirmation link.

## Create the lab IAM role

In IAM, choose **Roles → Create role → AWS service → EC2**. Attach `AmazonDynamoDBFullAccess` and `AmazonSNSFullAccess` where the exercise requires those lab policies. Name it `MovieMagic_role`. Attach its instance profile during launch or through **EC2 → Actions → Security → Modify IAM role**. If the lab supplies a preapproved role/profile or denies IAM creation, follow the lab instructions.

For a scoped deployment, replace the broad lab policies with the following policy. Replace `PARTITION`, `REGION`, `ACCOUNT` and the resource names with values for your lab. DynamoDB evaluates the underlying item actions for transactions. [DynamoDB IAM transactions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
      "Resource": "arn:PARTITION:dynamodb:REGION:ACCOUNT:table/MovieMagic_Users"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:BatchGetItem", "dynamodb:Scan"],
      "Resource": "arn:PARTITION:dynamodb:REGION:ACCOUNT:table/MovieMagic_Bookings"
    },
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:PARTITION:sns:REGION:ACCOUNT:MovieTicketNotifications"
    }
  ]
}
```

The role trust principal is `ec2.amazonaws.com` with action `sts:AssumeRole`. Continue with [EC2 deployment](DEPLOYMENT.md).
