# QEM-Bench

A reproducible, resource-aware benchmark of quantum error mitigation techniques, with a web results viewer and an
owner-only "Run Simulations" tab.

| Folder | What it is |
|---|---|
| `qem-bench/` | The Python/Qiskit research framework, experiments, paper and docs. Start with [`qem-bench/README.md`](qem-bench/README.md) |
| `backend/` | FastAPI API: published results, owner login and custom simulation runs |
| `frontend/` | React results viewer |
| `Dockerfile`, `deploy/`, `.github/workflows/deploy-lightsail.yml` | Production image, AWS Lightsail deploy scripts and the manual GitHub Actions deploy workflow |

**Deploying to AWS:** follow [`DEPLOY_AWS_LIGHTSAIL.md`](DEPLOY_AWS_LIGHTSAIL.md). After a one-time setup you deploy
from GitHub → Actions → *Deploy to AWS Lightsail* → *Run workflow*. The workflow runs the tests, smoke-tests the
image, then deploys to the Lightsail container service using a keyless AWS role, with MongoDB Atlas as the database.
The guide also covers moving to a custom domain later.

Run the production image locally:
```bash
docker build -t qem-bench .
docker run -p 8000:8000 -e MONGO_URL="mongodb+srv://..." -e DB_NAME=qem_bench \
  -e ADMIN_PASSWORD="choose-one" -e JWT_SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  -e CORS_ORIGINS=http://localhost:8000 qem-bench
# open http://localhost:8000
```
