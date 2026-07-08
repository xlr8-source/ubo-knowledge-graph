# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the UBO Knowledge Graph project, please report it responsibly. **Do not** open a public GitHub issue.

### How to Report

Please email security concerns to the project maintainers with:

- A clear description of the vulnerability
- Steps to reproduce (if possible)
- Potential impact and severity
- Any suggested fix or mitigation

We will acknowledge receipt of your report within 48 hours and work with you to understand and resolve the issue.

## Security Considerations

### Secrets & Credentials

- **Never commit `.env` files** — use `.env.example` as a template
- All API keys (Companies House, Neo4j) must be stored in environment variables
- Do not include credentials in logs or error messages
- Use `python config.py` to verify credentials are correctly loaded

### Data Sensitivity

- The UBO Knowledge Graph processes real UK corporate registry data
- Users should be aware that exported data may contain sensitive business information
- Ensure appropriate access controls when deploying the dashboard in shared environments

### Dependencies

- Keep Python packages up to date: `pip install --upgrade -r requirements.txt`
- Monitor security advisories for Neo4j, Streamlit, and other dependencies
- Report vulnerabilities in dependencies to their respective maintainers

## Security Best Practices

When using this project:

1. **Restrict network access** — If deploying the Streamlit dashboard, use authentication and VPNs where appropriate
2. **Database security** — Use Neo4j's built-in access controls and change default credentials
3. **API rate limits** — Respect Companies House API limits to avoid being throttled or blocked
4. **Regular backups** — Backup your Neo4j database regularly
5. **Keep Neo4j updated** — Install security patches for your Neo4j instance promptly

## Scope

This security policy applies to:

- The UBO Knowledge Graph codebase
- Core dependencies listed in `requirements.txt`

It does not cover:

- Third-party services (Neo4j, Companies House API, Streamlit Cloud)
- User deployments or customizations
- Infrastructure outside of this repository

## Disclosure Timeline

Once a vulnerability is confirmed:

1. We will develop a fix in a private branch
2. A security patch will be released with a CVE reference (if applicable)
3. Public disclosure will occur after a reasonable time to allow users to upgrade

We appreciate your responsible disclosure and help in keeping this project secure.
