# DreamProtocol Listmonk Deployment

This directory runs [Listmonk](https://listmonk.app/) with an internal Postgres database on the existing DreamProtocol leads/scraping VM. Amazon SES is used as the SMTP relay for outbound campaigns; **do not install or configure a raw SMTP server on this VM**.

- Initial admin port: `http://SERVER-IP:9000`
- Future public URL: `https://mail.getdreamprotocol.live`
- Sending domain: `getdreamprotocol.live`
- Main brand site: `https://dreamprotocol.ai`

> **Important:** the initial admin password comes from the VM-only `.env` file. Do not commit `.env`, and rotate the initial Listmonk admin password immediately after first login.

## 1. Prerequisites

- Docker installed on the VM.
- Docker Compose plugin installed (`docker compose version`).
- SES domain identity verified for `getdreamprotocol.live`.
- SES production access enabled for the AWS account/region.
- SES SMTP credentials created for the SES SMTP endpoint. These are **not** the same as AWS console/IAM login credentials.

## 2. Install

From the repo root on the VM:

```bash
cd deploy/listmonk
cp .env.example .env
nano .env
docker compose up -d
docker compose logs -f
```

Set strong VM-local values in `.env` before starting, especially:

- `POSTGRES_PASSWORD`
- `LISTMONK_ADMIN_PASSWORD`

The intended first admin username is:

```dotenv
LISTMONK_ADMIN_USER=admin
```

## 3. First login

Open:

```text
http://SERVER-IP:9000
```

Use the username and password from the VM-local `.env` file:

- Username: `LISTMONK_ADMIN_USER`
- Password: `LISTMONK_ADMIN_PASSWORD`

Rotate the admin password immediately after first login in the Listmonk admin UI.

## 4. SES SMTP setup in Listmonk

Do not put SES SMTP secrets in `docker-compose.yml`. Configure SMTP after login in the Listmonk admin UI under **Settings**.

Use these settings:

| Setting | Value |
| --- | --- |
| Host | `email-smtp.us-west-2.amazonaws.com` |
| Port | `587` |
| TLS | `STARTTLS` |
| Username | SES SMTP username |
| Password | SES SMTP password |
| From | `Dustin <dustin@getdreamprotocol.live>` |

The `.env.example` includes SES fields only as operator notes/reference. Keep real SES values in a secure password manager or VM-only secrets store, not in git.

## 5. DNS reminder

SPF should include both Microsoft 365 and Amazon SES:

```text
v=spf1 include:spf.protection.outlook.com include:amazonses.com ~all
```

Initial DMARC policy:

```text
v=DMARC1; p=none;
```

SES DKIM CNAME records must be added in DNS and verified in SES before sending production campaigns.

## 6. Security

- Do not expose Postgres publicly. This Compose file keeps Postgres internal to the Docker network and only publishes Listmonk on port `9000`.
- Use a strong `LISTMONK_ADMIN_PASSWORD` in the VM-local `.env` file.
- Do not commit `.env`.
- Temporarily use UFW to allow only SSH and Listmonk admin port `9000`:

  ```bash
  sudo ufw allow OpenSSH
  sudo ufw allow 9000/tcp
  sudo ufw enable
  sudo ufw status
  ```

- Later, put Listmonk behind an HTTPS reverse proxy or Cloudflare Tunnel at `https://mail.getdreamprotocol.live`.
- Rotate the initial admin password immediately after first login.

## 7. Backup

Run from `deploy/listmonk` or anywhere Docker can see the running containers:

```bash
docker exec listmonk-db pg_dump -U listmonk listmonk > listmonk-backup-$(date +%F).sql
```

If you change `POSTGRES_USER` or `POSTGRES_DB`, update the backup command accordingly.

## 8. Update

Run from `deploy/listmonk`:

```bash
docker compose pull
docker compose up -d
```

The app container runs Listmonk install idempotently and then upgrade before starting, so repeat `docker compose up -d` is safe for normal restarts/updates.

## 9. Deliverability

- Start with 10-20 emails/day.
- Prefer plain-text emails for early outreach.
- Include an unsubscribe link in every campaign.
- Suppress bounces and complaints promptly.
- Do not blast scraped lists immediately; warm up gradually and validate list quality first.

## Configuration notes

`config.toml` intentionally contains no real secrets. Database and admin credentials are injected at runtime from the VM-only `.env` file through Listmonk `LISTMONK_*` environment variables in `docker-compose.yml`.

Listmonk supports setting the initial Super Admin username and password with `LISTMONK_ADMIN_USER` and `LISTMONK_ADMIN_PASSWORD` during first install. The Compose command runs:

```bash
./listmonk --install --idempotent --yes --config /listmonk/config.toml && \
./listmonk --upgrade --yes --config /listmonk/config.toml && \
./listmonk --config /listmonk/config.toml
```
