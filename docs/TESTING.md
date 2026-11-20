# Testing

Run `python -m pytest -q` from the repository with the dev dependencies installed. Tests use temporary SQLite files, dummy identities and mocked AWS operations. No AWS account is needed.

The suite includes an AWS-mode checkout test with both services mocked and a Boto3 request-serialization check that intercepts the prepared DynamoDB request before network use.

| Area | Checks |
| --- | --- |
| Authentication | Registration, normalization, duplicate prevention, hashing, login count, CSRF, logout and protected routes |
| Discovery | Public pages, asset responses, movie-name search, city and genre filters, empty and error states |
| Checkout | 80-seat layout, show-scoped availability, invalid dates and seats, trusted prices, counter payment, PRG and concurrent reservation |
| Access | Ticket generation, owner-only access and booking history |
| AWS adapters | Conditional transaction shape, error mapping, unprocessed key retry, SNS recipient attributes and failed notifications |

## Browser smoke test

Verified the full local checkout in Microsoft Edge at 1440×1000 and 390×844. The run checked seat selection and deselection, displayed totals, ticket history, the print command and print stylesheet, and disabled seats after booking. It also checked for failed image, stylesheet, script or API requests and JavaScript exceptions. [Local screenshots](screenshots)

At desktop and mobile widths, register and log in, choose a city, filter a title, choose a theater, select a future date and time, and toggle two seats. Confirm the total and complete a demo payment. Open the ticket from history and inspect print preview. Return to the same show and verify the seats are disabled. A new showtime starts with its own availability.

## Lab acceptance

Use only synthetic customer data. Verify account and counter records, one booking plus its deterministic lock items, and a separate customer's inability to view the ticket. Verify the correct test inbox receives SNS messages and an unrelated filtered test inbox does not. Record actual results after the lab run.
