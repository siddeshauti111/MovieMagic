# EC2 deployment

Complete [AWS setup](AWS_SETUP.md), then create the instance in the same AWS region.

1. Launch an instance named **MovieMagic**. Use Amazon Linux 2023, Amazon Linux 2, or Ubuntu as available. Choose `t2.micro` or the lab-approved equivalent, a public subnet with internet access, and an automatically assigned public IPv4 address. Create an RSA key pair in PEM format if required and keep the private key off GitHub.
2. Attach `MovieMagic_role` as the instance profile. Prefer IMDSv2 required. Add TCP 5000 inbound from trusted presenter and viewer IPs only. For EC2 Instance Connect via the console, allow SSH from the region's EC2 Instance Connect service prefix list if available, or its published regional ranges. For direct SSH, use your trusted source IP. Allow outbound HTTPS and DNS as required. [EC2 Instance Connect setup](https://docs.aws.amazon.com/us_en/AWSEC2/latest/UserGuide/ec2-instance-connect-tutorial.html)
3. Wait for status checks. In EC2, select the instance, choose **Connect → EC2 Instance Connect**, then **Connect**. Use `ec2-user` for Amazon Linux or `ubuntu` for Ubuntu. Choose an AMI with EC2 Instance Connect installed or use the lab's connection instructions. [EC2 connection methods](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-methods.html)
4. Install Git and Python for the selected OS:

   **Amazon Linux 2023**

   ```bash
   sudo dnf install -y git python3.12 python3.12-pip
   python3.12 --version
   ```

   **Ubuntu**

   ```bash
   sudo apt update
   sudo apt install -y git python3 python3-venv python3-pip
   python3 --version
   ```

   **Amazon Linux 2**

   ```bash
   sudo yum install -y git gcc make openssl11-devel libffi-devel zlib-devel bzip2-devel xz-devel readline-devel sqlite-devel
   ```

   Install a lab-approved Python 3.11 or 3.12 interpreter. If needed, build a maintained Python 3.11 patch release from python.org, verify its published checksum, and install it in your home directory. With the verified source tarball already downloaded, substitute its version below:

   ```bash
   PYVER=3.11.REPLACE_WITH_PATCH
   tar xf "Python-${PYVER}.tgz"
   cd "Python-${PYVER}"
   ./configure --prefix="$HOME/.local"
   make -j2
   make altinstall
   "$HOME/.local/bin/python3.11" -c 'import ssl, sqlite3'
   ```

   AL2023 or Ubuntu is simpler for a time-limited lab if offered.

5. Clone your GitHub repository and create the virtual environment. Use `python3.12` or `$HOME/.local/bin/python3.11` in place of `python3` for the installs above.

   ```bash
   git clone https://github.com/siddeshauti111/MovieMagic.git
   cd MovieMagic
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   umask 077
   cp .env.example .env
   python -c 'import secrets; print(secrets.token_hex(32))'
   nano .env
   ```

   Set `APP_MODE=aws`, the generated persistent `FLASK_SECRET_KEY`, `AWS_REGION`, the `SNS_TOPIC_ARN`, and `FLASK_DEBUG=0`. Keep the default table names unless your deployment uses different names. Set `COOKIE_SECURE=0` for the HTTP lab with test credentials, or `1` when using HTTPS. Check SNS setup before enabling detailed email. Avoid placing credentials in shell history or supplying AWS access keys.

6. Start Flask as your regular user with the required lab command:

   ```bash
   flask --app app:create_app run --host=0.0.0.0 --port=5000
   ```

   Open `http://EC2_PUBLIC_IP:5000`. The Flask development server is intended for a temporary demonstration. The public address can change or stop responding when the instance shuts down or the lab expires.

## Optional Gunicorn, systemd and Nginx

For a direct lab demonstration after stopping Flask, use:

```bash
gunicorn --workers 2 --bind 0.0.0.0:5000 'app:create_app()'
```

For HTTPS, bind Gunicorn to `127.0.0.1:5000`, enable secure cookies, and terminate TLS on Nginx with your valid hostname and certificate. Allow inbound HTTPS and remove the public 5000 rule. Configure your HTTPS Nginx server block to forward requests:

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

For a persistent service where allowed, create `/etc/systemd/system/moviemagic.service` with the correct username and absolute checkout path. Restrict access to the project directory and its `.env`.

```ini
[Unit]
Description=MovieMagic Gunicorn
After=network-online.target
[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/MovieMagic
ExecStart=/home/ec2-user/MovieMagic/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:create_app()
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

Run `sudo systemctl daemon-reload`, then `sudo systemctl enable --now moviemagic`. Check `sudo journalctl -u moviemagic` for startup issues. In the lab, verify health, user records, booking records and matching inbox receipt using synthetic data.
