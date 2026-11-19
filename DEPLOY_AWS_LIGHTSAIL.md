# Deploying QEM-Bench to AWS Lightsail (container service + MongoDB Atlas)

This guide takes you from the GitHub repository to a live QEM-Bench site on **Amazon Lightsail container service**,
with the database on **MongoDB Atlas (free tier)**. Section 10 explains how to move to your own domain later.

---

## 0. What you are deploying

```
Browser ──HTTPS──▶ Lightsail public endpoint (managed TLS, load balancer)
                     │
                     ▼  HTTP :8000
              ┌──────────────────────────────────────────┐
              │ container "app"  (Dockerfile in repo root)│
              │  • FastAPI  /api/*                         │
              │  • built React viewer  /                   │
              │  • Qiskit Aer simulator (runs as a         │
              │    subprocess for "Run Simulations")       │
              │  • published results baked into the image  │
              └───────────────┬──────────────────────────┘
                              │ mongodb+srv (TLS)
                              ▼
                   MongoDB Atlas (free M0 cluster)
                   • owner login attempts (lockout)
                   • custom run records
                   • custom run result tables (GridFS)
```

* **One image, one container, one node.** The website and the API share one address, so you don't need CORS or a
  separate frontend host.
* **Nothing important is stored on the container's disk.** Lightsail containers lose their disk on every redeploy.
  When a simulation run finishes, its tables, summary, spec and log are copied into MongoDB Atlas. Raw per-shot Parquet
  files are temporary scratch data, and the results tables are rebuilt from them before they are deleted.
* **About "the server IP":** Lightsail *container services* do not hand out a fixed IP address. Instead you get a
  permanent HTTPS address like `https://qem-bench.abc123xyz.us-east-1.cs.amazonlightsail.com`. That is the address
  you use until you add your own domain (section 10). It already has a valid TLS certificate, so the owner
  password is never sent in plain text.

### Cost (as of 2026, check the [pricing page](https://aws.amazon.com/lightsail/pricing/))

| Power | vCPU | RAM | USD / month | Suitability |
|---|---|---|---|---|
| small | 0.5 | 1 GB | ~$15 | works; simulations run about 2× slower |
| **medium** (recommended) | 1 | 2 GB | ~$40 | comfortable for designs up to the 20,000-unit limit |
| large | 2 | 4 GB | ~$80 | only if many people run simulations |

MongoDB Atlas M0 is free (512 MB storage, which is plenty: a typical run stores well under 1 MB).

> **Keep the scale at 1 node.** The "one simulation at a time" rule and the live progress tracking live inside the
> single container process. Adding nodes would let two runs start at once.

---

## 1. Prerequisites on your Mac

| Tool | Install | Check |
|---|---|---|
| Git | `xcode-select --install` | `git --version` |
| Docker Desktop | https://www.docker.com/products/docker-desktop/ (start it) | `docker buildx version` |
| AWS CLI v2 | `brew install awscli` | `aws --version` |
| Lightsail container plugin (`lightsailctl`) | `brew install aws/tap/lightsailctl` | `lightsailctl --version` |
| Python 3 | ships with macOS / `brew install python` | `python3 --version` |

`lightsailctl` is required by `aws lightsail push-container-image`. On Apple Silicon (M1–M4) the deploy script builds
for `linux/amd64` automatically, because Lightsail runs x86-64 containers.

---

## 2. Get the code from GitHub

1. In Emergent, click **Save to GitHub** to push the project to your repository.
2. On your Mac:
   ```bash
   git clone https://github.com/<your-user>/<your-repo>.git qem-bench-app
   cd qem-bench-app
   ```
   The repository root contains `Dockerfile`, `backend/`, `frontend/`, `qem-bench/` and `deploy/lightsail/`.

---

## 3. Create the MongoDB Atlas database (free)

1. Sign up at https://www.mongodb.com/cloud/atlas/register.
2. **Create a cluster**: choose **M0 (Free)**, provider **AWS**, and the **same region** you will use for Lightsail
   (e.g. `us-east-1` / N. Virginia). Name it `qem-bench`.
3. **Database Access → Add New Database User**: authentication *Password*, username `qembench`, click
   *Autogenerate Secure Password* and **copy it**. Role: *Read and write to any database*.
4. **Network Access → Add IP Address → Allow access from anywhere (`0.0.0.0/0`)**.
   Lightsail container services don't have a fixed outbound IP, so Atlas can't allow-list a single address.
   The database is still protected by the user/password and TLS. Use the long generated password.
5. **Database → Connect → Drivers → Python**. Copy the connection string, which looks like
   `mongodb+srv://qembench:<password>@qem-bench.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=qem-bench`.
   Replace `<password>` with the password from step 3. If the password contains `@ : / ? # [ ] %`, URL-encode it,
   for example with `python3 -c "import urllib.parse;print(urllib.parse.quote_plus('PASTE'))"`.

The app creates its collections (`custom_runs`, `login_attempts`, `run_files.*`) on first start.

---

## 4. Give the AWS CLI access to Lightsail

1. Sign in to the AWS console and open **IAM → Users → Create user**, e.g. `qem-bench-deployer`
   (no console access needed).
2. **Permissions → Attach policies directly → Create policy → JSON**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{ "Effect": "Allow", "Action": "lightsail:*", "Resource": "*" }]
   }
   ```
   Name it `LightsailFullAccess` and attach it to the user.
3. Open the user → **Security credentials → Create access key → Command Line Interface (CLI)**. Copy both values.
4. On your Mac:
   ```bash
   aws configure
   # AWS Access Key ID:     <paste>
   # AWS Secret Access Key: <paste>
   # Default region name:   us-east-1        (any Lightsail region; match Atlas)
   # Default output format: json
   aws lightsail get-regions --query 'regions[].name' --output text   # should list regions
   ```

---

## 5. Fill in the deployment settings

```bash
cp deploy/lightsail/lightsail.env.example deploy/lightsail/lightsail.env
python3 -c "import secrets; print(secrets.token_hex(32))"     # copy the output for JWT_SECRET
open -e deploy/lightsail/lightsail.env                        # or: nano deploy/lightsail/lightsail.env
```

| Variable | What to put |
|---|---|
| `AWS_REGION` | the region from step 4, e.g. `us-east-1` |
| `SERVICE_NAME` | `qem-bench` (lowercase letters, digits, hyphens; it becomes part of the URL) |
| `SERVICE_POWER` | `medium` (or `small` to save money) |
| `MONGO_URL` | the Atlas connection string from step 3 |
| `DB_NAME` | `qem_bench` |
| `ADMIN_PASSWORD` | a **new**, long password for the *Run Simulations* tab. Don't reuse the preview password |
| `JWT_SECRET` | the 64 hex characters you just generated |
| `CORS_ORIGINS` | leave the placeholder for now; you will set it in step 7 |

`lightsail.env` is git-ignored, so it never goes to GitHub.

---

## 6. First deployment (one command)

```bash
chmod +x deploy/lightsail/deploy.sh
./deploy/lightsail/deploy.sh --create
```

The script:

1. creates the container service (`--power medium --scale 1`) and waits until it is `READY` (about 3–5 min, first
   time only);
2. builds the image for `linux/amd64` from the root `Dockerfile` (about 5–10 min the first time; later builds are
   cached);
3. pushes it to the service's private registry (`aws lightsail push-container-image`);
4. creates a deployment from `deploy/lightsail/deployment.template.json` with your environment variables, using health
   check `GET /api/health`;
5. waits for the deployment to go `ACTIVE` and prints the public URL, then runs a health check (`{"ok":true}`).

<details><summary>Prefer the console instead of the script for steps 1 and 4?</summary>

* **Create service:** Lightsail console → *Containers* → *Create container service* → choose a region, power
  *Medium*, scale *1*, name `qem-bench` → *Create*.
* **Push the image:** still run `docker buildx build --platform linux/amd64 -t qem-bench:latest --load .` and
  `aws lightsail push-container-image --service-name qem-bench --label app --image qem-bench:latest`.
* **Deployment:** *qem-bench → Deployments → Create your first deployment*. Container name `app`. Choose the stored
  image `:qem-bench.app.N`. Open port `8000` / HTTP. Add the environment variables `MONGO_URL`, `DB_NAME`,
  `ADMIN_PASSWORD`, `JWT_SECRET` and `CORS_ORIGINS`. Set the public endpoint to container `app` on port 8000 with
  health check path `/api/health`.
</details>

---

## 7. Check the live site

1. Open the printed URL (also on the Lightsail console under *Containers → qem-bench*), e.g.
   `https://qem-bench.abc123xyz.us-east-1.cs.amazonlightsail.com`.
2. The Overview, Explorer, Statistics, Figures and Reproducibility tabs should show the published study.
3. Open **Run Simulations**, sign in with your `ADMIN_PASSWORD` and start a small run (e.g. `bell_cx`, `moderate`,
   1,024 shots, 5 repetitions). It should finish in a few seconds on *medium*.
4. Put the real URL into `CORS_ORIGINS` in `lightsail.env` and redeploy once: `./deploy/lightsail/deploy.sh`.
   The site works without this because it is same-origin, but it limits which other websites can call the API.

Persistence test: redeploy (`./deploy/lightsail/deploy.sh`) and confirm your finished run still opens with its table.
That shows it is being served from Atlas.

---

## 8. Everyday operations

| Task | Command |
|---|---|
| Ship new code | `git pull && ./deploy/lightsail/deploy.sh` |
| Live logs | `aws lightsail get-container-log --service-name qem-bench --container-name app` |
| Service status / URL | `aws lightsail get-container-services --service-name qem-bench` |
| Change password or secrets | edit `lightsail.env`, then `./deploy/lightsail/deploy.sh` |
| Bigger machine | `aws lightsail update-container-service --service-name qem-bench --power large` |
| Roll back | console → *qem-bench → Deployments → Deployment history* → pick a previous version → *Modify and redeploy* |
| Pause billing permanently | `aws lightsail delete-container-service --service-name qem-bench` (Atlas data stays) |

Each push creates a new stored image (`:qem-bench.app.1`, `.2`, …). Lightsail keeps a limited number, so delete old
ones under *Images* if it complains.

Updating the **published** results (e.g. after `scripts/reproduce_all.sh` and the viewer export) means rebuilding the
image, because those files are baked in: commit, push, `./deploy/lightsail/deploy.sh`.

---

## 9. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `push-container-image` says *lightsailctl not found* | install the plugin (section 1) and open a new terminal |
| Deployment goes `FAILED` straight away | read `get-container-log`. `KeyError: 'MONGO_URL'` (or another name) means a variable is missing from `lightsail.env` |
| Logs show `ServerSelectionTimeoutError` | Atlas *Network Access* is missing `0.0.0.0/0`, or the password in `MONGO_URL` is wrong or not URL-encoded |
| `exec format error` in the logs | the image was built for arm64. The script forces `--platform linux/amd64`; don't push a plain `docker build` image from an M-series Mac |
| Sign-in says *Too many failed attempts* | 5 wrong passwords from one client, or 20 in total, lock sign-in for 15 minutes |
| Run marked *failed: Server restarted during the run* | a redeploy or crash happened mid-run. Start it again |
| Runs feel slow | move from `small` to `medium` (section 8) |

---

## 10. Moving to your own domain later

You can do this at any time. The Lightsail URL keeps working alongside the new domain.

### 10.1 Register a domain

Either option works:

* **In Lightsail (simplest):** console → **Domains & DNS → Register domain**. Search a name such as
  `qem-bench.org`, pay, and wait for the confirmation email. Lightsail then creates a **DNS zone** for it
  automatically.
* **Any other registrar** (Namecheap, Cloudflare, Google/Squarespace, GoDaddy…): buy the domain there. Then
  either (a) keep DNS at that registrar, or (b) in Lightsail create a DNS zone with
  `aws lightsail create-domain --domain-name qem-bench.org --region us-east-1` and change the domain's
  **nameservers** at the registrar to the four `ns-*.awsdns-*` servers shown in the zone. Nameserver changes can take
  up to 48 h, usually under 1 h.

### 10.2 Create a TLS certificate for the container service

Console: **Containers → qem-bench → Custom domains → Create certificate**. Enter `qem-bench.org` and
`www.qem-bench.org`.
CLI equivalent:
```bash
aws lightsail create-certificate --certificate-name qem-bench-cert \
    --domain-name qem-bench.org --subject-alternative-names www.qem-bench.org
aws lightsail get-certificates --certificate-name qem-bench-cert \
    --query 'certificates[0].certificateDetail.domainValidationRecords[].resourceRecord'
```
The certificate stays *Pending validation* until you add the **CNAME validation records** it lists:

* DNS in Lightsail: *Domains & DNS → your zone → DNS records → Add record → CNAME*, and paste each name and value.
* DNS at another registrar: add the same CNAME records in its DNS panel.

Validation usually completes in 5–30 minutes (status *Valid*).

### 10.3 Attach the domain and point DNS at it

1. Console: **Containers → qem-bench → Custom domains → Attach certificate** → pick `qem-bench-cert` → select both
   names → *Attach*. CLI:
   ```bash
   aws lightsail update-container-service --service-name qem-bench \
     --public-domain-names '{"qem-bench-cert": ["qem-bench.org", "www.qem-bench.org"]}'
   ```
2. Create the DNS records that send traffic to the service:
   * **Lightsail DNS zone:** add an **A record** for `@` (the bare domain) and choose *Alias* → your container service
     `qem-bench`. Add an A-alias or a **CNAME** for `www` pointing to the service's default host
     (`qem-bench.abc123xyz.us-east-1.cs.amazonlightsail.com`).
   * **Other DNS provider:** add a **CNAME** for `www` pointing to the default host. Most providers do not allow a
     CNAME on the bare domain. Use their *ALIAS/ANAME/CNAME-flattening* record if they have one (Cloudflare does).
     Otherwise use the provider's "redirect bare domain → www" feature.
3. Wait a few minutes, then open `https://qem-bench.org` and `https://www.qem-bench.org`.

### 10.4 Finish the switch

1. In `deploy/lightsail/lightsail.env` set
   `CORS_ORIGINS=https://qem-bench.org,https://www.qem-bench.org,https://qem-bench.abc123xyz.us-east-1.cs.amazonlightsail.com`.
2. Redeploy: `./deploy/lightsail/deploy.sh`.
3. Update links in `qem-bench/README.md`, the paper's data-availability statement and anywhere you have shared the URL.
4. Optional: once everyone is using the domain, remove the long Lightsail URL from `CORS_ORIGINS`. Lightsail still
   serves it, but other sites can no longer call the API through it.

Nothing else changes. Data stays in Atlas, the frontend calls `/api` on whatever domain served the page, and no
rebuild is needed for the domain itself.

---

## 11. Security checklist

* Use a production `ADMIN_PASSWORD` and `JWT_SECRET` that differ from the preview environment. Changing
  `JWT_SECRET` signs everyone out.
* Lightsail stores container environment variables in the deployment definition. Anyone with Lightsail access in your
  AWS account can read them, so keep IAM access to yourself.
* Atlas: keep the generated database password, and turn on Atlas backups (paid tiers) or a periodic `mongodump` if
  your custom runs matter long-term.
* The image runs as a non-root user (`uid 10001`) and does not contain `.env` files, tests, the paper or the
  `.git` folder (see `.dockerignore`).
