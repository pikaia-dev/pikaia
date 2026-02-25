# SOC 2 / ISO 27001 Compliance Checklist

> Assessment date: 2026-02-25
> Scope: Pikaia, Prelint, Tango Finance, supporting AWS infrastructure
> AWS accounts: `403682862630` (tango-admin), `507481515916` (snowball-prod), `498155006695` (tango-b2b-demo)

## How to read this

Items are grouped into three tiers:

1. **Quick wins** — low effort, no performance/business impact, do them now
2. **Known how-to but painful** — we know the solution, but it costs time, money, or affects workflow
3. **Hard / costly** — requires significant investment, external vendors, or organizational change

Each item is tagged with the relevant framework controls:
- `SOC2-CC` = SOC 2 Common Criteria
- `SOC2-A` = Availability, `SOC2-C` = Confidentiality, `SOC2-PI` = Processing Integrity, `SOC2-P` = Privacy
- `ISO-A.x` = ISO 27001:2022 Annex A control

Status: `[ ]` = not done, `[~]` = partially done, `[x]` = done

---

## Current strengths (already passing)

These are controls you can present evidence for today:

- [x] **Authentication via Stytch B2B** — MFA, SSO/SAML, SCIM, passkeys, magic links `SOC2-CC6.1` `ISO-A.8.5`
- [x] **RBAC enforcement** — admin/member roles, `require_admin` decorator, privilege escalation checks `SOC2-CC6.3` `ISO-A.8.3`
- [x] **Audit logging** — `AuditLog` model with actor, IP, user-agent, diff, correlation ID, immutable `SOC2-CC7.2` `ISO-A.8.15`
- [x] **Structured logging** — JSON in production, per-request correlation IDs, Datadog-compatible `SOC2-CC7.2` `ISO-A.8.15`
- [x] **Secrets in AWS Secrets Manager** — no hardcoded prod secrets, injected via ECS task definition `SOC2-CC6.1` `ISO-A.8.9`
- [x] **Production startup validation** — app refuses to start with insecure defaults or missing secrets `SOC2-CC6.1`
- [x] **HTTPS everywhere** — HSTS 1yr + preload, SSL redirect, secure cookies `SOC2-CC6.1` `ISO-A.8.24`
- [x] **Security headers** — X-Frame-Options DENY, Content-Type nosniff, strict referrer, CORP `SOC2-CC6.1`
- [x] **Webhook signature verification** — Stripe (native), Stytch (Svix), custom (HMAC-SHA256 + timestamp) `SOC2-CC6.1`
- [x] **Webhook idempotency** — `ProcessedWebhook` unique constraint prevents replay `SOC2-PI1.3`
- [x] **SSRF protection** — domain allowlist + DNS resolution check, blocks metadata endpoint `SOC2-CC6.1` `ISO-A.8.23`
- [x] **SVG sanitization** — defusedxml + lxml to prevent XSS via uploads `SOC2-CC6.1`
- [x] **File upload validation** — size limits, MIME type + magic number check `SOC2-CC6.1`
- [x] **Non-root containers** — multi-stage Docker builds, `appuser` in runtime `SOC2-CC6.1` `ISO-A.8.25`
- [x] **CI/CD with OIDC** — no static AWS credentials in GitHub Actions `SOC2-CC6.1` `ISO-A.8.9`
- [x] **SAST in CI** — bandit security scanner runs on every push/PR `SOC2-CC7.1` `ISO-A.8.28`
- [x] **Dependency vulnerability scanning** — pip-audit in CI `SOC2-CC7.1` `ISO-A.8.8`
- [x] **Database encryption at rest** — Aurora `storage_encrypted=True` `SOC2-CC6.1` `ISO-A.8.24`
- [x] **Database encryption in transit** — RDS Proxy `require_tls=True` `SOC2-CC6.1` `ISO-A.8.24`
- [x] **Deletion protection** — Aurora cluster deletion protection enabled `SOC2-A1.2` `ISO-A.8.13`
- [x] **Automated backups** — Aurora 7-day retention, snapshot on stack deletion `SOC2-A1.2` `ISO-A.8.13`
- [x] **Soft deletes + hard delete for GDPR** — `SoftDeleteModel` + explicit `hard_delete()` `SOC2-P1.1` `ISO-A.8.10`
- [x] **Multi-tenant isolation** — `TenantScopedModel` with mandatory org FK, org-scoped queries `SOC2-CC6.3` `ISO-A.8.3`
- [x] **CloudWatch monitoring + alarms** — error rate, latency, CPU, memory, DB connections, SNS alerts `SOC2-CC7.2` `ISO-A.8.16`
- [x] **WAF (Pikaia)** — rate limiting, OWASP CRS, IP reputation, known bad inputs, origin verification `SOC2-CC6.6` `ISO-A.8.23`
- [x] **Pre-commit hooks** — ruff, biome, mypy, conventional commits, large file prevention `SOC2-CC8.1` `ISO-A.8.25`
- [x] **Architecture Decision Records** — 9 ADRs documenting security-relevant decisions `ISO-A.5.1`
- [x] **SECURITY.md** — vulnerability disclosure/reporting policy `SOC2-CC7.3` `ISO-A.5.5`
- [x] **Pydantic schema validation** — all API I/O validated, no raw SQL `SOC2-PI1.2` `ISO-A.8.25`
- [x] **CORS scoped** — `CORS_ALLOWED_ORIGINS` explicitly configured per environment `SOC2-CC6.1`

---

## Tier 1: Quick wins (low effort, no business impact)

### Credentials & secrets hygiene

- [ ] **Rotate AWS IAM key in tango-finance .env** — `AKIAV...DWDVY3` appears to be a real key. Rotate immediately via AWS IAM console, update local `.env`. `SOC2-CC6.1` `ISO-A.8.9`
- [ ] **Rotate QuickBooks client secret in tango-finance .env** — real secret found in plaintext. `SOC2-CC6.1` `ISO-A.8.9`
- [ ] **Move ~/private.pem and ~/id_ed into ~/.ssh/** — private keys should not sit in home directory root. Set `chmod 600`. `ISO-A.8.9`
- [ ] **Remove auth token from ~/.sentryclirc** — use `SENTRY_AUTH_TOKEN` env var or `sentry-cli login` with token stored in keychain. `ISO-A.8.9`
- [ ] **Audit all .env files for real credentials** — ensure test credentials are clearly prefixed with `test`, document which are safe to keep locally. `SOC2-CC6.1` `ISO-A.8.9`

### Documentation (write once, reuse for both frameworks)

- [ ] **Write an incident response plan** — even a 1-page doc: who gets paged, escalation path, communication template, post-mortem process. `SOC2-CC7.3` `SOC2-CC7.4` `ISO-A.5.24` `ISO-A.5.25` `ISO-A.5.26`
- [ ] **Write a data retention policy** — audit logs kept forever (already documented in observability.md), user data retention period, backup retention, log retention. Just formalize what you already do. `SOC2-CC6.5` `SOC2-P1.1` `ISO-A.8.10`
- [ ] **Write a brief access control policy** — who can access AWS console, GitHub repos, production DB, Stytch dashboard, Stripe dashboard. Document current state. `SOC2-CC6.2` `SOC2-CC6.3` `ISO-A.5.15` `ISO-A.8.2`
- [ ] **Add privacy policy and terms of service for Pikaia** — tango-finance has one, Pikaia does not. `SOC2-P1.1` `SOC2-P1.2` `ISO-A.5.34`
- [ ] **Document the change management process** — it's already enforced (PR-based, CI gates, conventional commits), just write it down. `SOC2-CC8.1` `ISO-A.8.32`
- [ ] **Document the onboarding/offboarding process** — Stytch SCIM handles provisioning, but document the steps: grant AWS access, add to GitHub org, add to Slack, etc. `SOC2-CC6.2` `ISO-A.6.1` `ISO-A.6.5`

### Quick code/config fixes

- [ ] **Fix `ALLOWED_HOSTS = *` in ECS** — set it to your actual domain(s). Currently mitigated by ALB host header checks but an auditor will flag it. `SOC2-CC6.1` `ISO-A.8.23`
- [ ] **Add `.env` to a global gitignore** — you have project-level `.gitignore` entries, but add `~/.gitignore_global` as a safety net. `ISO-A.8.9`
- [ ] **Enable CloudTrail if not already on** — AWS management events should be logged. Check if it's enabled on all 3 accounts. `SOC2-CC7.2` `ISO-A.8.15`
- [ ] **Enable S3 access logging** — for media buckets, so you can prove who accessed what. `SOC2-CC7.2` `ISO-A.8.15`

---

## Tier 2: Known how-to, affects workflow or costs money

### Infrastructure hardening

- [ ] **Enable AWS GuardDuty** — threat detection for all accounts. ~$30-50/mo for small workloads. Straightforward to enable but generates alerts you need to triage. `SOC2-CC7.2` `ISO-A.8.16`
- [ ] **Implement admin IP allowlist** — restrict `/admin/` to known IPs or VPN. `SOC2-CC6.1` `ISO-A.8.20`
- [ ] **Add second NAT gateway** — for high availability. Currently single NAT = single AZ failure takes down outbound traffic. Doubles NAT cost (~$30/mo extra). `SOC2-A1.2` `ISO-A.8.14`
- [ ] **Enable automated snapshots for cross-region DR** — Aurora supports cross-region replicas. ~$20-50/mo for storage. `SOC2-A1.2` `ISO-A.8.13` `ISO-A.8.14`
- [ ] **Set up AWS Config rules** — automated compliance checking (e.g., S3 buckets must be encrypted, security groups must not allow 0.0.0.0/0). ~$2/rule/region/mo. `SOC2-CC7.1` `ISO-A.8.9`

### Process establishment

- [ ] **Quarterly access reviews** — review who has access to AWS, GitHub, Stytch, Stripe, production DB. Document the review in a spreadsheet/ticket. Takes 1-2 hours per quarter but auditors require evidence. `SOC2-CC6.2` `SOC2-CC6.3` `ISO-A.5.15` `ISO-A.8.2`
- [ ] **Quarterly dependency updates** — you already scan for vulns in CI, but auditors want to see a regular cadence of updates with evidence (PRs/tickets). `SOC2-CC7.1` `ISO-A.8.8`
- [ ] **Vendor risk register** — list all third-party services (Stytch, Stripe, Resend, Sentry, AWS, GitHub, Vercel if used) with their SOC 2 reports and data they process. `SOC2-CC9.2` `ISO-A.5.19` `ISO-A.5.20` `ISO-A.5.21`
- [ ] **Risk assessment** — formal document identifying top risks, likelihood, impact, mitigations. Can be a simple spreadsheet. Required annually for ISO 27001, expected for SOC 2. `SOC2-CC3.1` `SOC2-CC3.2` `ISO-A.5.2` `ISO-A.5.3`
- [ ] **Endpoint security policy** — require disk encryption (FileVault), screen lock, OS updates on developer machines. Consider MDM if team grows. `SOC2-CC6.7` `ISO-A.8.1`
- [ ] **MFA on all SaaS accounts** — AWS (check IAM), GitHub, Stytch dashboard, Stripe dashboard, Sentry, domain registrar. Document which accounts have MFA enabled. `SOC2-CC6.1` `ISO-A.8.5`
- [ ] **Security awareness training** — even for a small team, document that it happens. Can be as simple as a quarterly 30-min session covering phishing, credential hygiene, incident reporting. `SOC2-CC1.4` `ISO-A.6.3`

### Testing & validation

- [ ] **Add E2E tests** — Playwright is mentioned in roadmap. Not strictly required for SOC 2, but auditors love seeing comprehensive test suites. More importantly, it validates auth flows and RBAC in a real browser. `SOC2-CC8.1` `ISO-A.8.29`
- [ ] **Run a vulnerability scan / pentest** — can start with automated tools (OWASP ZAP, nuclei) against staging. A real pentest costs $5-15k but carries weight with auditors. `SOC2-CC4.1` `ISO-A.8.8`

---

## Tier 3: Hard / costly (significant investment)

### Formal compliance programs

- [ ] **Engage a SOC 2 auditor** — CPA firm, $20-50k for Type II audit. Need 3-6 month observation window. Consider Type I first if you need to move fast. `SOC2-CC1.1` through `SOC2-CC9.2`
- [ ] **ISO 27001 certification body** — accredited auditor, $15-40k. Requires formal ISMS (Information Security Management System) with defined scope, policy hierarchy, management review minutes. `ISO-4` through `ISO-10`
- [ ] **Compliance automation platform** — Vanta, Drata, or Secureframe ($10-30k/yr). Automates evidence collection, policy management, continuous monitoring. Dramatically reduces ongoing effort but significant annual cost. Worth it if customers require SOC 2 reports. `SOC2-CC4.2` `ISO-A.5.36`

### Organizational controls

- [ ] **Business continuity / disaster recovery plan** — document RTO/RPO targets, failover procedures, communication plan, test annually. For Aurora this means: cross-region read replica, tested restore from snapshot, DNS failover. `SOC2-A1.2` `SOC2-A1.3` `ISO-A.5.29` `ISO-A.5.30` `ISO-A.8.13` `ISO-A.8.14`
- [ ] **Formal ISMS (ISO 27001 requirement)** — information security policy, scope statement, Statement of Applicability, management review process, internal audit program. This is the bulk of ISO 27001 overhead. `ISO-4` `ISO-5` `ISO-6` `ISO-7` `ISO-8` `ISO-9` `ISO-10`
- [ ] **Data Processing Agreements (DPAs)** — with all sub-processors (AWS, Stytch, Stripe, Resend, Sentry). Most already offer standard DPAs you just need to sign/accept. `SOC2-P1.1` `ISO-A.5.20`
- [ ] **Dedicated security role** — even part-time, someone who owns the compliance program, runs access reviews, manages risk register, coordinates audits. `SOC2-CC1.3` `ISO-A.5.2`
- [ ] **Log aggregation / SIEM** — CloudWatch works but a proper SIEM (Datadog Security, AWS Security Hub, or similar) provides correlation, alerting on anomalies, and retention management. $200-2000/mo depending on volume. `SOC2-CC7.2` `ISO-A.8.15` `ISO-A.8.16`
- [ ] **Penetration testing program** — annual pentest by a qualified third party, with formal report and remediation tracking. $10-25k/yr. `SOC2-CC4.1` `ISO-A.8.8`

---

## Recommended priority order

**This week (Tier 1 — credentials):**
1. Rotate the AWS IAM key in tango-finance
2. Move private keys to proper locations
3. Clean up sentryclirc
4. Audit all .env files

**This month (Tier 1 — documentation):**
5. Write incident response plan
6. Write access control policy
7. Write data retention policy
8. Document change management process
9. Fix `ALLOWED_HOSTS`
10. Enable CloudTrail on all accounts

**Next quarter (Tier 2 — infrastructure + process):**
11. Enable GuardDuty
12. First quarterly access review
13. Build vendor risk register
14. Write risk assessment
15. Add privacy policy to Pikaia

**When ready to pursue certification (Tier 3):**
16. Evaluate compliance platforms (Vanta/Drata/Secureframe)
17. Engage SOC 2 Type I auditor
18. Build BCP/DR plan
19. Schedule first pentest
