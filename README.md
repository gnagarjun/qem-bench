# QEM-Bench

A reproducible, resource-aware benchmark of quantum error mitigation techniques, with a web results viewer and an
owner-only "Run Simulations" tab.

| Folder | What it is |
|---|---|
| `qem-bench/` | The Python/Qiskit research framework, experiments, paper and docs. Start with [`qem-bench/README.md`](qem-bench/README.md) |
| `backend/` | FastAPI API: published results, owner login and custom simulation runs |
| `frontend/` | React results viewer |
| `Dockerfile`, `deploy/lightsail/` | Production image and AWS Lightsail deployment scripts |

**Deploying to AWS:** follow [`DEPLOY_AWS_LIGHTSAIL.md`](DEPLOY_AWS_LIGHTSAIL.md). It covers the Lightsail container
service with MongoDB Atlas and moving to a custom domain later.

Run the production image locally:
```bash
docker build -t qem-bench .
docker run -p 8000:8000 -e MONGO_URL="mongodb+srv://..." -e DB_NAME=qem_bench \
  -e ADMIN_PASSWORD="choose-one" -e JWT_SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  -e CORS_ORIGINS=http://localhost:8000 qem-bench
# open http://localhost:8000
```
