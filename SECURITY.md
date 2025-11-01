# Security Policy

## Project Status

ScholarFlux is currently in **beta** (v0.1.3). While we remain committed to security and will address vulnerabilities as they become known, please be aware:

- This is pre-release software under active development
- APIs and interfaces may change between versions
- Security patches will be incorporated as vulnerabilities are discovered
- We encourage security researchers to help us identify and fix issues

Starting from version v0.1.0, we will release patches for security vulnerabilities as they are reported.

**Note:** As we move toward a stable 1.0 release, we will establish a more formal security support timeline.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

We take security seriously, even during beta. Please report security vulnerabilities by:

1. **Email:** scholar.flux@gmail.com
2. **GitHub Security Advisories:** Use the "Security" tab in this repository

We aim to respond within 72 hours. As this is a beta project under active development, response times may vary, but we are committed to addressing security concerns promptly.

Please include the following information in your report:
- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability, including how an attacker might exploit it

**Beta Disclosure:** Given the pre-release status, we may address critical vulnerabilities immediately in the main branch. Less critical issues will be tracked and resolved in subsequent releases.

## Security Considerations

### API Keys and Credentials

ScholarFlux interacts with various academic databases and APIs that may require authentication:

- **Never hardcode API keys** in your code or commit them to version control
- Use environment variables or secure credential management systems
- Leverage the built-in `.env` support via `python-dotenv`
- Rotate API keys regularly
- Use read-only or minimal-privilege API keys when possible

**Example secure configuration:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('ACADEMIC_API_KEY')
```

### Caching Security

ScholarFlux uses `requests-cache` with security features:

- Cached responses may contain sensitive data
- Use encrypted cache backends when storing sensitive information
- Consider cache expiration policies for sensitive queries
- The `cryptography` extra provides additional cache encryption options
- Be mindful of cached credentials in shared environments

**Recommendation:**
```python
# Use SQLite cache for sensitive data instead of in-memory or regular file-system-cache
from requests_cache import CachedSession

session = CachedSession(
    'scholar_cache',
    user_agent='scholar flux search'
    backend='sqlite',
    expire_after=3600,
)
```

**Or for further encryption security using `cryptography` and `safer_serializer`:**
```python
# Import the cached session manager factor class
from scholar_flux.sessions import EncryptionPipelineFactory, CachedSessionManager
from scholar_flux.api import SearchAPI
import os

# Attempts to load encryption key from environment 
# variable or keep track of it:
key = os.environ.get("SCHOLAR_FLUX_CACHE_SECRET_KEY")

# Recreates new key if it is None from the previous step
encryption_pipeline_factory = EncryptionPipelineFactory(key)

if not key:
    # Save this key to the environment variable for future use
    # CRITICAL: Store this key securely - losing it means losing cached data
    current_key = encryption_pipeline_factory.secret_key 

# Create a new encryption serializer
serializer = encryption_pipeline_factory()

# Creates a cached session manager with encryption
manager = CachedSessionManager(backend='sqlite', user_agent='scholar flux search', serializer=serializer)

# uses the manager class to creates a new CachedSession 
session = manager()

# creates a basic response retrieval session to use as a part of a final search coordinator or separately
api = SearchAPI(query = 'security best practices', session = session)
```

### Security Notes:

**Never commit encryption keys to version control**
Rotate encryption keys periodically
If the encryption key is lost, cached data cannot be recovered
Use different keys for development and production environments
Consider key management systems (AWS KMS, HashiCorp Vault) for production

### Database Connections

If using the `database` extra (SQLAlchemy, Redis, MongoDB):

- **Never use default credentials** in production
- Use connection string encryption
- Implement proper authentication and authorization
- Use TLS/SSL for database connections
- Follow the principle of least privilege for database users
- Regularly update database drivers

### Input Validation

ScholarFlux uses Pydantic for data validation:

- All user inputs are validated before processing
- API responses are parsed and validated
- Type checking prevents injection attacks
- However, always sanitize data before database queries

### XML/YAML Parsing

When using the `parsing` extra:

- XML parsing uses `xmltodict` - be aware of XML External Entity (XXE) attacks
- YAML parsing uses `PyYAML` - only parse trusted YAML sources
- Never parse untrusted XML/YAML without proper validation
- Consider using safe loading methods

### Dependency Security

We regularly monitor and update dependencies:

- All dependencies are tracked in `poetry.lock`
- We use `requests` with security best practices
- Optional extras (`cryptography`, `database`, `parsing`) are isolated
- Run `poetry update` regularly to get security patches
- Monitor GitHub Security Advisories for this repository

## Best Practices for Users

### Beta Software Notice
As ScholarFlux is in beta:
- Test thoroughly in development environments before production use
- Monitor the repository for updates and security advisories
- Report any security concerns you discover
- Stay updated with the latest beta releases
- Understand that breaking changes may occur between beta versions

### 1. Keep Dependencies Updated
```bash
poetry update
```

### 2. Use Virtual Environments
Always use isolated environments to prevent dependency conflicts:
```bash
poetry install
poetry shell
```

### 3. Minimal Installations
Only install extras you need:
```bash
# Only install what you use
poetry install --extras "database"
```

### 4. Rate Limiting
Respect API rate limits to avoid service disruptions:
- Implement exponential backoff
- Cache responses appropriately
- Use the built-in caching features

### 5. Error Handling
Don't expose sensitive information in error messages:
- Sanitize stack traces in production
- Log security events appropriately
- Never log API keys or credentials

### 6. Network Security
When querying external academic databases:
- Use HTTPS connections only
- Verify SSL certificates
- Be aware of man-in-the-middle attacks
- Consider using VPNs or institutional network access

## Known Security Limitations

### Third-Party API Dependencies
- ScholarFlux relies on external academic APIs
- Security of data depends on third-party providers
- API availability and authentication methods may change
- Users are responsible for complying with API terms of service

### Data Privacy
- Scholarly data may contain personal information
- Users must comply with relevant data protection regulations (GDPR, CCPA, etc.)
- Be mindful of caching personally identifiable information
- Consider data retention policies

### Rate Limiting
- Excessive requests may result in IP blocking by academic databases
- Implement appropriate rate limiting in your applications
- Respect robots.txt and API usage policies

## Security Updates

As a beta project, we are committed to:
- Responding to reported vulnerabilities within 72 hours
- Incorporating security patches into subsequent releases
- Addressing critical vulnerabilities as quickly as possible
- Crediting security researchers (unless they prefer to remain anonymous)
- Maintaining transparency about known security issues

**Development Timeline:**
- **Beta (current):** Security fixes incorporated as vulnerabilities are discovered
- **Stable 1.0+:** Formal security advisory system and regular patch schedule

We appreciate the security community's patience and collaboration as we work toward a stable release.

## Responsible Disclosure

We follow a coordinated disclosure policy adapted for beta software:
1. Security researchers report vulnerabilities privately
2. We acknowledge receipt within 72 hours
3. We work with researchers to understand and validate the issue
4. We develop and test a fix
5. For critical vulnerabilities: immediate patch to main branch
6. For non-critical issues: inclusion in next release with security notes
7. We publicly credit the researcher (with their permission)

**Beta Consideration:** Given the active development nature of this project, fixes may be deployed more rapidly than in stable software, and we may coordinate disclosure timing based on severity and fix complexity.

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python-security.readthedocs.io/vulnerabilities.html)
- [Requests Security](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification)

## Contact

For security concerns, please contact:
- **Primary:** Use GitHub Security Advisories (Security tab in this repository)
- **Alternative:** Open a private discussion or contact the maintainers
- **Public discussions:** Only for non-sensitive security topics

---

**Note:** This security policy reflects our commitment to security during beta development and is subject to change as the project matures. Please check back regularly for updates.
