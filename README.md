![sample image](mysecretsanta.png)

Invite your buddies and do a secret santa draw. Trust me, it will be really random. Like, quantum physics level of random

## Dev environment

You'll need the following in your dev machine to get started

* [uv](https://docs.astral.sh/uv/)
* Docker (CLI and daemon) with Compose

### Clone the repository and `cd` into it
```
git clone git@github.com:prithajnath/my-secret-santa.git && cd my-secret-santa
```
### Install dependencies

```
$ uv sync
```
### Start the services

This starts the API (on https://localhost:9100), Postgres with PostGIS, Redis and the Celery worker. Migrations run when the web container starts.

```
$ docker compose up --build -d
```

### Run the tests

The tests use [pytest-postgresql](https://github.com/dbfixtures/pytest-postgresql) to create a throwaway PostGIS database per test on the compose Postgres server, so run them in a container on the compose network:

```
$ docker compose run --rm --no-deps --entrypoint bash secret-santa-web \
    -c "uv sync --frozen --group dev -q && pytest tests"
```

Set `TEST_DATABASE_URL` to point them at a different PostGIS server.

### Add the pre-commit hook
The hook checks that `uv.lock` matches `pyproject.toml` and that `requirements.txt` matches `uv.lock`

```
git config core.hooksPath .githooks
```
If `requirements.txt` is out of sync, update it and try committing again

```
$ uv export --format requirements.txt --no-dev -o requirements.txt
```

## Admin panel

This service only serves the REST API (`/api`) and the admin panel (`/admin`); the web app is the separate Next.js frontend, and `/` redirects to it. Admins log in at `/admin/login/` with a username and password. To create an admin, or set a password for an existing one (e.g. an account made with Google sign-in):

```
$ flask createsuperuser
$ flask set-password <username>
```

## REST API

The application includes a REST API layer for modern frontend frameworks (React, Next.js, etc.) with JWT authentication.

### API Documentation

Interactive Swagger documentation is available at:
```
https://localhost:9100/api/docs/
```

### Authentication

The API uses JWT Bearer tokens. Include the token in the `Authorization` header:
```
Authorization: Bearer <your_access_token>
```

### Endpoints Overview

| Category | Endpoints |
|----------|-----------|
| Auth | `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` |
| OAuth | `/api/auth/oauth/google/url`, `/api/auth/oauth/google/callback` |
| Users | `/api/users/me`, `/api/users/<username>` |
| Groups | `/api/groups`, `/api/groups/<id>`, `/api/groups/<id>/members`, `/api/groups/<id>/pairs` |
| Messages | `/api/groups/<id>/messages`, `/api/pairs/<channel_id>/messages` |
| Santa | `/api/santa`, `/api/santa/reveal` |

### Quick Start

```javascript
// Login
const res = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'user', password: 'password' })
});
const { data } = await res.json();
const token = data.access_token;

// Use authenticated endpoints
const groups = await fetch('/api/groups', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## Google OAuth Integration

The API supports Google OAuth for sign-in/sign-up using the token exchange pattern.

### Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google+ API
3. Create OAuth 2.0 credentials (Web application)
4. Add your frontend callback URL to **Authorized redirect URIs** (e.g., `https://yourapp.com/oauth/callback`)
5. Set environment variables:
   ```bash
   export GOOGLE_CLIENT_ID="your-client-id"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   ```

### OAuth Flow

#### Step 1: Get OAuth URL

```javascript
const redirectUri = `${window.location.origin}/oauth/callback`;
const res = await fetch(
  `/api/auth/oauth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}`
);
const { data } = await res.json();

// Redirect user to Google
window.location.href = data.oauth_url;
```

#### Step 2: Handle Callback

After the user authorizes, Google redirects to your callback URL with a `code` parameter:

```javascript
// On your /oauth/callback page
const handleOAuthCallback = async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');

  const res = await fetch('/api/auth/oauth/google/callback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code,
      redirect_uri: `${window.location.origin}/oauth/callback`
    })
  });

  const { data } = await res.json();

  // Store tokens
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);

  // Check if new user for onboarding
  if (data.user.is_new_user) {
    router.push('/welcome');
  } else {
    router.push('/dashboard');
  }
};
```

### Response

```json
{
  "success": true,
  "data": {
    "user": {
      "id": 123,
      "username": "john",
      "email": "john@gmail.com",
      "first_name": "John",
      "last_name": "Doe",
      "avatar_url": "https://...",
      "is_new_user": false
    },
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

### Notes

- New users are automatically created on first Google login
- Username is auto-generated from Google profile name
- `is_new_user` flag helps identify first-time users for onboarding flows
- The `redirect_uri` must match exactly in both the URL request and callback exchange

### NOTE: NGINX

Initially I exposed gunicorn workers to direct Internet traffic from ELB. This setup suffered multiple worker shutdowns. Most suggestions online said I needed to use a gevent or eventlet worker pool but I decided to expose an NGINX container to ELB traffic and send that traffic upstream (gunicorn workers). Almost immediately I saw drastically better response times

EDIT: I migrated to an L7 load balancer so I could do HTTPS redirects, which caused some regression in the benchmark numbers so I ended up adding gevent workers because almost all of the work in this app is I/O bound

Before gevent

```
loadtest  -n 1000 -c 6 -k https://app.mysecretsanta.io
```

```
INFO 
INFO Target URL:          https://app.mysecretsanta.io
INFO Max requests:        10000
INFO Concurrency level:   6
INFO Agent:               keepalive
INFO 
INFO Completed requests:  10000
INFO Total errors:        0
INFO Total time:          421.516164677 s
INFO Requests per second: 24
INFO Mean latency:        252.7 ms
INFO 
INFO Percentage of the requests served within a certain time
INFO   50%      248 ms
INFO   90%      261 ms
INFO   95%      279 ms
INFO   99%      318 ms
INFO  100%      1066 ms (longest request)

```

After gevent

```
loadtest -n 1000 -c 100 -k https://app.mysecretsanta.io
```

```
INFO Requests: 0 (0%), requests per second: 0, mean latency: 0 ms
INFO 
INFO Target URL:          https://app.mysecretsanta.io
INFO Max requests:        1000
INFO Concurrency level:   100
INFO Agent:               keepalive
INFO 
INFO Completed requests:  1000
INFO Total errors:        0
INFO Total time:          4.762389858000001 s
INFO Requests per second: 210
INFO Mean latency:        457.4 ms
INFO 
INFO Percentage of the requests served within a certain time
INFO   50%      277 ms
INFO   90%      1133 ms
INFO   95%      1290 ms
INFO   99%      1423 ms
INFO  100%      1453 ms (longest request)
```


### Backups

1. Create backup file called `backup.sql` in prod 
```
docker exec my-secret-santa_secret-santa-web_1 'pg_dump -a -h secret-santa-postgres -U postgres postgres > backup.sql
```

2. Transfer it to whatever machine using SFTP

```
sftp santa-ec2
Connected to santa-ec2.
sftp> get backup/backup.sql 
Fetching /home/ubuntu/backup/backup.sql to backup.sql
backup.sql                                                                                                                                                                                                  100%  260KB 997.4KB/s   00:00    
sftp> exit
```

3. Bring this file to new server and copy it to the running web container

```
docker cp backup.sql my-secret-santa_secret-santa-web_1:/usr/bin/secretsanta

```
4. restore db with `psql`

```
psql -h secret-santa-postgres -U postgres --db postgres -f backup.sql

```