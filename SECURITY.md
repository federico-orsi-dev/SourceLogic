# Security Policy

This is a portfolio demonstration. Do not use hardcoded secrets in production. Report vulnerabilities via GitHub Issues.

## Scope

This repository contains demonstration projects intended for engineering portfolio review, not production deployment.

## Supported Usage

- Local development and technical assessment.
- Architecture and documentation review.

## Vulnerability Reporting

Please open a GitHub Issue with:

- A clear title (`[SECURITY] <summary>`).
- Affected project and file path.
- Reproduction steps and expected impact.
- Suggested mitigation, if available.

## Secret Management Rules

- Never commit real credentials, tokens, or private endpoints.
- Use `.env.example` placeholders only.
- Load secrets from environment variables or a secret manager (for example HashiCorp Vault).
