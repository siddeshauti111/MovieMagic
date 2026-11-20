# Viva questions

**Why are there three logical entities and two DynamoDB tables?**  
Users and bookings require mutable cloud persistence. Movies use a shared read-only catalog file. Booking ownership and movie references remain logical relationships.

**Why use email as the user partition key?**  
A normalized email needs one keyed read during login. A conditional put prevents duplicates even if two requests arrive together.

**What makes a seat unique?**  
The movie, theater, date, time and seat number. The show dimensions are hashed and combined with a seat label in a deterministic key.

**What if one of several seats is already booked?**  
One conditional write fails and DynamoDB cancels the entire transaction. SQLite rolls back the complete unit of work under the same condition.

**What prevents a customer from lowering the price in the browser?**  
The backend resolves the selected theater and calculates the price from the catalog. The browser's displayed total is for feedback.

**How does EC2 get AWS credentials?**  
Boto3 uses its default credential provider chain and obtains temporary credentials through the attached EC2 instance profile.

**How does SNS keep ticket details private?**  
Each authorized subscription matches a recipient attribute derived from the normalized account email. Every subscription must be audited and filtering verified before detailed messages are enabled.

**What if SNS fails after checkout?**  
The confirmed booking and seat locks persist. The ticket reports that email delivery could not be confirmed.

**Why use a scan for booking history?**  
The required schema has only a booking ID partition key. A filtered paginated scan fits demonstration data. A larger deployment could add an owner index with a time sort key.

**What differs between HTTPS and the lab HTTP endpoint?**  
TLS protects login and session traffic. The temporary HTTP demo uses test data and restricted inbound access. HTTPS deployments enable secure cookies.
