# Deploying QEM-Bench to AWS Lightsail with GitHub Actions

This guide takes you from your GitHub repository to a live QEM-Bench site on an **Amazon Lightsail container
service**, with the database on **MongoDB Atlas (free tier)**. Deploys run from **GitHub Actions** when you
press a button. GitHub signs in to AWS through a trusted link (OpenID Connect), so **no AWS keys are stored
anywhere**. Section 9 explains how to move to your own domain later.

**The short version, once set up:** GitHub → **Actions** → **Deploy to AWS Lightsail** → **Run workflow**.

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
  you use until you add your own domain (section 9). It already has a valid TLS certificate, so the owner
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


### What the workflow does (`.github/workflows/deploy-lightsail.yml`)

```
Run workflow (manual, branch main)
  └─ job "tests"   : uv + Python 3.11 → full qem-bench pytest suite (unit, integration, scientific, reproducibility)
       │ any failure → stop, nothing is deployed
  └─ job "deploy"  : build the Docker image (linux/amd64, cached between runs)
                     → start it next to a throw-away MongoDB and run deploy/ci/smoke_test.sh
                       (site loads, published data, owner login, one tiny simulation)
                     → sign in to AWS with the trusted role (no stored keys)
                     → create the Lightsail service on first use, push the image, roll out a deployment
                     → wait until ACTIVE, then check the live site (health, pages, data, login; no simulation)
```

A failed test or smoke check stops the workflow before anything reaches AWS. A failed Lightsail rollout leaves the
previous version serving traffic, and the workflow prints the container log.

---

## 1. Put the code on GitHub

1. click **Save to GitHub** and choose or create your repository (for example `you/qem-bench`).
2. Make sure the default branch is **`main`**. The workflow only deploys from `main`, and the AWS trust in step 3 is
   limited to that branch.

The repository root must contain `Dockerfile`, `.github/workflows/deploy-lightsail.yml`, `backend/`, `frontend/`,
`qem-bench/` and `deploy/`.

---

## 2. Create the MongoDB Atlas database (free)

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

## 3. One-time AWS setup: let your repository deploy (no keys)

You do this once, in the browser, using **AWS CloudShell** (a terminal built into the AWS console).

1. Sign in to the AWS console as an administrator and pick your region in the top-right (for example **N. Virginia,
   us-east-1**, ideally the same as Atlas).
2. Click the **CloudShell** icon (`>_`) in the top bar and wait for the prompt.
3. Paste these lines, replacing `you/qem-bench` with your GitHub `owner/repository`:
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/you/qem-bench/main/deploy/lightsail/setup-github-oidc.sh
   bash setup-github-oidc.sh you/qem-bench main
   ```
   If the repository is private, the `curl` will fail. Instead open `deploy/lightsail/setup-github-oidc.sh` on GitHub,
   click **Raw**, copy everything, run `nano setup-github-oidc.sh` in CloudShell, paste, press `Ctrl+O`, `Enter`,
   `Ctrl+X`, and run the `bash` line.
4. The script:
   * registers GitHub (`token.actions.githubusercontent.com`) as a trusted identity provider in your account (only if
     it isn't already);
   * creates the role **`qem-bench-github-deploy`**, which **only** workflows from `you/qem-bench` on branch `main`
     can use;
   * allows that role Lightsail actions only (`lightsail:*`), with no access to the rest of AWS.
5. It finishes by printing a role ARN like `arn:aws:iam::123456789012:role/qem-bench-github-deploy`. **Copy it.**

If you rename the repository or deploy from another branch, run the script again with the new values. It updates the
role.

---

## 4. Add the settings to GitHub

In your repository: **Settings → Secrets and variables → Actions**.

**Secrets** tab → **New repository secret** (hidden values):

| Name | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | the role ARN from step 3 |
| `MONGO_URL` | the Atlas connection string from step 2 |
| `ADMIN_PASSWORD` | a new, long owner password for the *Run Simulations* tab. Don't reuse the preview password |
| `JWT_SECRET` | 64 random hex characters, e.g. from `python3 -c "import secrets; print(secrets.token_hex(32))"` or run `openssl rand -hex 32` in CloudShell |

**Variables** tab → **New repository variable** (visible values):

| Name | Value |
|---|---|
| `AWS_REGION` | `us-east-1` (the region you chose in step 3) |
| `LIGHTSAIL_SERVICE_NAME` | `qem-bench` (lowercase letters, digits and hyphens; becomes part of the URL) |
| `LIGHTSAIL_POWER` | `medium` (or `small` to save money; only used when the service is first created) |
| `DB_NAME` | `qem_bench` |
| `CORS_ORIGINS` | for the first deploy put `https://example.invalid`; you will replace it with the real URL in step 6 |

If any of these are missing, the workflow stops at **Check settings** and names the missing one.

---

## 5. Deploy: press the button

1. Repository → **Actions** tab. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
2. Click **Deploy to AWS Lightsail** in the list on the left, then **Run workflow** → branch **main** → **Run workflow**.
3. Watch the two jobs:
   * **Research test suite**: about 2–4 minutes.
   * **Build, smoke-test and deploy**: about 10–15 minutes the first time, because the service is created and the
     image built from scratch. Later runs take about 5–8 minutes thanks to the build cache.
4. When it is green, open the run. The **summary** shows `Deployed to https://qem-bench.xxxxxxxx.us-east-1.cs.amazonlightsail.com/`.

Only people with write access to the repository can press **Run workflow**.

---

## 6. Check the live site

1. Open the URL from the workflow summary (also on the Lightsail console under *Containers → qem-bench*).
2. The Overview, Explorer, Statistics, Figures and Reproducibility tabs should show the published study.
3. Open **Run Simulations**, sign in with your `ADMIN_PASSWORD` and start a small run (e.g. `bell_cx`, `moderate`,
   1,024 shots, 5 repetitions). It should finish in a few seconds on *medium*.
4. Set the GitHub variable `CORS_ORIGINS` to that URL without the trailing slash (e.g.
   `https://qem-bench.xxxxxxxx.us-east-1.cs.amazonlightsail.com`) and run the workflow once more.
5. Persistence check: after that redeploy, your finished run should still open with its table. That shows it is
   being served from Atlas.

---

## 7. Everyday operations

| Task | How |
|---|---|
| Ship new code | push or merge to `main` (e.g. **Save to GitHub**), then **Actions → Deploy to AWS Lightsail → Run workflow** |
| Change the owner password or other secrets | edit the GitHub secret or variable, then run the workflow |
| See logs | Lightsail console → *Containers → qem-bench → Logs*, or in CloudShell: `aws lightsail get-container-log --service-name qem-bench --container-name app` |
| Service status / URL | Lightsail console → *Containers*, or `aws lightsail get-container-services --service-name qem-bench` |
| Bigger machine | console → *qem-bench → Capacity → Change capacity*, or `aws lightsail update-container-service --service-name qem-bench --power large` |
| Roll back | console → *qem-bench → Deployments → Deployment history* → pick a previous version → *Modify and redeploy*. Or re-run an older successful workflow run (*Actions → run → Re-run all jobs*), which redeploys that commit |
| Stop paying | `aws lightsail delete-container-service --service-name qem-bench` (Atlas data stays; the next workflow run recreates the service) |

Each push creates a new stored image (`:qem-bench.app.1`, `.2`, …). Lightsail keeps a limited number, so delete old
ones under *Images* if it complains.

Updating the **published** results (e.g. after `scripts/reproduce_all.sh` and the viewer export) means rebuilding the
image, because those files are baked in: commit, push, run the workflow.

Storage: each finished run keeps its tables in Atlas (usually 20–500 KB). *Remove* in the viewer only hides a run, and
its files stay, so you can recover it. The free M0 tier's 512 MB holds roughly a thousand typical runs. To free space,
delete hidden runs in Atlas (*Browse Collections*): remove the `custom_runs` documents with `deleted: true` and the
`run_files.files` and `run_files.chunks` entries whose filename starts with that `run_id`.

---

## 8. Troubleshooting

| Where it fails | Likely cause and fix |
|---|---|
| **Check settings** | the named secret or variable is missing or misspelled (step 4). Names are case-sensitive |
| **Research test suite** | a real test failure. Open the log, fix it, push and run again. Nothing was deployed |
| **Smoke-test the image** | the image doesn't start or a check fails. The step prints the container log (`docker logs`) |
| **Sign in to AWS**: *Not authorized to perform sts:AssumeRoleWithWebIdentity* | the role trust doesn't match. Check the repository name and branch, and re-run `setup-github-oidc.sh owner/repo main`. Also check that you ran the workflow on `main` |
| **Sign in to AWS**: *No OpenIDConnect provider found* | step 3 wasn't run in this AWS account |
| **Push image and deploy**: *AccessDenied* on a `lightsail:` action | the role's inline policy is missing. Re-run the setup script |
| **Push image and deploy**: deployment `FAILED` | the step prints the container log. `ServerSelectionTimeoutError` means Atlas *Network Access* is missing `0.0.0.0/0`, or the password in `MONGO_URL` is wrong or not URL-encoded. `KeyError: 'X'` means variable X is missing |
| **Check the live site** fails but the deploy is ACTIVE | usually the `ADMIN_PASSWORD` secret changed since the last deploy, or sign-in is locked after failed attempts. Wait 15 minutes and re-run |
| Sign-in on the site says *Too many failed attempts* | 5 wrong passwords from one client, or 20 in total, lock sign-in for 15 minutes |
| Run marked *failed: Server restarted during the run* | a deploy or crash happened mid-run. Start it again |
| Runs feel slow | move from `small` to `medium` (section 7) |

---

## 9. Moving to your own domain later

You can do this at any time. The Lightsail URL keeps working alongside the new domain.

### 9.1 Register a domain

Either option works:

* **In Lightsail (simplest):** console → **Domains & DNS → Register domain**. Search a name such as
  `qem-bench.org`, pay, and wait for the confirmation email. Lightsail then creates a **DNS zone** for it
  automatically.
* **Any other registrar** (Namecheap, Cloudflare, Google/Squarespace, GoDaddy…): buy the domain there. Then
  either (a) keep DNS at that registrar, or (b) in Lightsail create a DNS zone with
  `aws lightsail create-domain --domain-name qem-bench.org --region us-east-1` and change the domain's
  **nameservers** at the registrar to the four `ns-*.awsdns-*` servers shown in the zone. Nameserver changes can take
  up to 48 h, usually under 1 h.

### 9.2 Create a TLS certificate for the container service

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

### 9.3 Attach the domain and point DNS at it

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

### 9.4 Finish the switch

1. In GitHub, set the variable
   `CORS_ORIGINS=https://qem-bench.org,https://www.qem-bench.org,https://qem-bench.abc123xyz.us-east-1.cs.amazonlightsail.com`.
2. Run the **Deploy to AWS Lightsail** workflow.
3. Update links in `qem-bench/README.md`, the paper's data-availability statement and anywhere you have shared the URL.
4. Optional: once everyone is using the domain, remove the long Lightsail URL from `CORS_ORIGINS`. Lightsail still
   serves it, but other sites can no longer call the API through it.

Nothing else changes. Data stays in Atlas, the frontend calls `/api` on whatever domain served the page, and no
rebuild is needed for the domain itself.

---

## 10. Security checklist

* Use a production `ADMIN_PASSWORD` and `JWT_SECRET` that differ from the preview environment. Changing
  `JWT_SECRET` signs everyone out.
* Lightsail stores container environment variables in the deployment definition. Anyone with Lightsail access in your
  AWS account can read them, so keep IAM access to yourself.
* Atlas: keep the generated database password, and turn on Atlas backups (paid tiers) or a periodic `mongodump` if
  your custom runs matter long-term.
* The image runs as a non-root user (`uid 10001`) and does not contain `.env` files, tests, the paper or the
  `.git` folder (see `.dockerignore`).
* GitHub can only reach AWS through the `qem-bench-github-deploy` role. That role is limited to Lightsail, and only
  workflows on `main` of your repository can use it. To revoke access, delete the role in IAM.
* Secrets are never printed in the workflow logs (GitHub masks them). The workflow file's permissions are read-only
  apart from `id-token: write`, which is required for the trusted link.

---

## Appendix A: deploy from your Mac instead (optional)

The same script the workflow uses also runs locally.

1. Install Docker Desktop, the AWS CLI (`brew install awscli`) and the Lightsail plugin
   (`brew install aws/tap/lightsailctl`). Then sign in with `aws configure`, using an IAM user that has `lightsail:*`,
   or `aws configure sso`.
2. `cp deploy/lightsail/lightsail.env.example deploy/lightsail/lightsail.env` and fill in the same values as step 4
   (`SERVICE_NAME`, `SERVICE_POWER`, …). The file is git-ignored.
3. `./deploy/lightsail/deploy.sh`, which builds a linux/amd64 image, creates the service if needed, pushes and deploys.
   `./deploy/lightsail/deploy.sh build` only builds. `./deploy/lightsail/deploy.sh release` pushes an already-built
   `qem-bench:latest`.
4. To smoke-test the image locally first:
   `docker run -d --name qem -p 8000:8000 -e MONGO_URL=... -e DB_NAME=test -e ADMIN_PASSWORD=pw -e JWT_SECRET=$(openssl rand -hex 32) -e CORS_ORIGINS=http://127.0.0.1:8000 qem-bench:latest`
   and then `bash deploy/ci/smoke_test.sh http://127.0.0.1:8000 pw`.
