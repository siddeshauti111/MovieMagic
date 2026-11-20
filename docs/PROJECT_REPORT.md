# MovieMagic project report

## Problem and objectives

A digital booking system needs searchable cinema schedules, a clear price and seat selection, and reliable confirmation when customers compete for the same seats. MovieMagic demonstrates that end-to-end flow in a temporary cloud lab and an offline development environment.

## Entity relationship diagram

Users and Movies each have a one-to-many relationship with Bookings. Each booking owns one or more seat locks. Refer to [the architecture diagrams](ARCHITECTURE.md) for logical attributes, keys and physical storage mapping.

## Prerequisites and project flow

Use Python 3.9+, Git and a browser locally. The cloud demonstration requires authorized AWS access and a permitted region. A customer registers, signs in, searches by city and genre, selects a show and seats, completes a simulated payment, and opens a ticket or booking history.

## Epic 1 · Web application development and setup

Flask serves Jinja2 pages with responsive CSS and JavaScript seat controls. A JSON catalog supplies prices and schedules. SQLite provides local persistence.

## Epic 2 · AWS account setup

The application can be deployed in an authorized AWS account, including a temporary lab account. See [AWS setup](AWS_SETUP.md).

## Epic 3 · DynamoDB database creation and setup

The user table conditionally inserts records by normalized email. The bookings table stores confirmed tickets and deterministic seat-lock records. A transaction commits every seat and its booking together.

## Epic 4 · SNS notification setup

Flask publishes after commit. A message attribute matches the subscription filter for the account email. Local mode simulates notification, and SNS errors change notification status independently of the booking.

## Epic 5 · IAM role setup

The EC2 instance profile grants DynamoDB and SNS access. The setup guide includes the lab role and an optional scoped policy.

## Epic 6 · EC2 instance setup

The instance runs in a VPC with a public IPv4 address and restricted security-group rules. See [deployment](DEPLOYMENT.md).

## Epic 7 · Deployment using EC2

Clone the GitHub repository, install dependencies in a virtual environment and configure AWS mode. Run Flask on port 5000 for the temporary demo. Gunicorn and Nginx are optional for a managed service and TLS.

## Epic 8 · Testing and deployment

The automated suite exercises authentication, discovery, checkout, concurrent access, ticket ownership and mocked AWS integrations. See [testing](TESTING.md) for results and the live lab acceptance procedure.

## Results and limitations

The local workflow produces a saved ticket and simulated notification. The deployment guide prepares the same workflow for live AWS. Fictional listings, simulated payments, lab-scale capacity and manual SNS subscription setup limit the application to demonstrations.

## Conclusion

MovieMagic demonstrates password-protected booking, transactional seat allocation and confirmation status across local and cloud configurations using the documented architecture.
