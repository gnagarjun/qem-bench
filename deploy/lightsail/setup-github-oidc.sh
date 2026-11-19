#!/usr/bin/env bash
# One-time AWS setup so GitHub Actions can deploy without stored AWS keys (OpenID Connect).
# Run it in AWS CloudShell (console, top bar ">_" icon) or any terminal signed in as an AWS admin:
#   bash setup-github-oidc.sh <github-owner>/<repo> [branch]
# Prints the role ARN to save as the GitHub secret AWS_DEPLOY_ROLE_ARN.
set -euo pipefail
REPO="${1:?usage: $0 <owner>/<repo> [branch]}"
BRANCH="${2:-main}"
ROLE="qem-bench-github-deploy"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
PROVIDER_ARN="arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"

if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  echo "==> Registering GitHub as an identity provider in this AWS account"
  aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
fi

TRUST=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "${PROVIDER_ARN}"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:${REPO}:ref:refs/heads/${BRANCH}"
      }
    }
  }]
}
JSON
)
POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"lightsail:*","Resource":"*"}]}'

if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  echo "==> Updating trust policy of existing role $ROLE"
  aws iam update-assume-role-policy --role-name "$ROLE" --policy-document "$TRUST"
else
  echo "==> Creating role $ROLE (only ${REPO} on branch ${BRANCH} can use it)"
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" \
    --description "GitHub Actions deploys QEM-Bench to Lightsail" >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name lightsail-deploy --policy-document "$POLICY"

echo
echo "Done. Save this as the GitHub repository secret AWS_DEPLOY_ROLE_ARN:"
aws iam get-role --role-name "$ROLE" --query Role.Arn --output text
