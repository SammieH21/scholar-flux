# Security Policy

## Project Status

ScholarFlux is currently in **beta** (v0.6.0). While we remain committed to security and will address vulnerabilities as they become known, please be aware:

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

### Internal Secret Management

ScholarFlux masks sensitive data at multiple levels:

- **ConfigLoader** wraps API keys in `SecretStr` objects—they won't leak via `repr()` or `str()`
- **SensitiveDataMasker** pattern-matches API keys, database URIs, and private keys before they hit logs
- **MaskingFilter** scrubs any remaining sensitive strings from log output
- **SettingsDict** uses `scholar_flux.security.masker` to mask plain-text secrets before being printed to console environments

Even if you accidentally log a config object, credentials stay masked:

```python
import logging
from scholar_flux.utils import ConfigLoader

logger = logging.getLogger('scholar_flux')
logger.setLevel(logging.DEBUG)

config_settings = ConfigLoader()
config_settings.load_config(reload_env=True)

# Even if the entire config is logged, secrets are masked
logger.debug(f"Config: {config_settings.config}")
# OUTPUT: Config: {'PUBMED_API_KEY': '**********', 'SCHOLAR_FLUX_DEFAULT_MAILTO': '**********', ...}
```

You can also register custom patterns:

```python
from scholar_flux import masker

# Add a custom pattern to mask
masker.add_sensitive_string_patterns(
    name="internal_ids",
    patterns=r"INTERNAL-[A-Z0-9]{8}",
    use_regex=True
)
print(masker.mask_text("INTERNAL-12345678"))
# OUTPUT: '***'
```

Several patterns are automatically masked on startup via `SensitiveDataMasker._register_api_defaults()`, including, but not limited to the following:

- `api[-_]key=`
- `secret[-_]key=`
- `mailto:***`
- `password`
- `URI credentials`
- `'sk-'/'sk-ant-' credentials`

### API Key-Based Authentication & Transmission

ScholarFlux handles credential storage at rest and credential use as distinct responsibilities. The `SearchAPI` uses a provider-specific authentication lifecycle (`AuthAPIKeyParameter`, `AuthAPIKeyHeader`) for handling key-based authentication methods.

1. **On `SearchAPI` initialization**: Keys are validated (i.e., type, length) and masked via the `SearchAPIConfig`. If an API key is unassigned but required for a provider, a warning is raised on initialization completion.
2. **When the user performs a record search**: The `SearchAPI.search()` creates an `AuthAPIKeyParameter` or `AuthAPIKeyHeader` to validate and mask API keys/tokens.
3. **After building the request**: The `AuthAPIKeyParameter`/`AuthAPIKeyHeader` unmasks and injects the key or token into the `requests.PreparedRequest` URL query or headers based on the configuration. The request is transmitted to the API provider immediately afterward.

**Note**: To opt out when a key is available or otherwise required (e.g., request mocking, configuration testing), use `AuthAPIKeyNoOp` to send a request without API key injection.

```python
from scholar_flux import SearchAPI

api = SearchAPI(query="test", provider_name="crossref")

# Handled internally by `SearchAPI.search()` when a token is available or required
auth = api.build_auth()

# Key is masked at rest. None is returned when not required otherwise.
print(auth)
# AuthAPIKeyHeader(api_key=**********, parameter_name='CROSSREF-PLUS-API-TOKEN', scheme='Bearer')

# Key is only unmasked when auth(prepared_request) is called during request dispatch
```

Provider configuration settings declare **how** keys should be transmitted (`api_key_in_headers`, `api_key_parameter`, `api_key_scheme`, `api_key_required`, `api_key_env_var`). The `SearchAPI` uses these provider-specific configuration settings to determine whether to transmit the API key via request `headers` or `params`.

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
    user_agent='scholar flux search',
    backend='sqlite',
    expire_after=3600,
)
```

**Or for further encryption security using `cryptography` and `safer_serializer`:**
```python
# Import the cached session manager factor class
from scholar_flux.sessions import EncryptionPipelineFactory, CachedSessionManager
from scholar_flux.api import SearchAPI
from scholar_flux import config_settings

# Attempts to load an encryption key from the `SCHOLAR_FLUX_CACHE_SECRET_KEY` environment variable when available
encryption_pipeline_factory = EncryptionPipelineFactory()
env_var = "SCHOLAR_FLUX_CACHE_SECRET_KEY"

# If the key was not previously read from the OS environment
if not config_settings.get(env_var):

    print("Created a new secret key. **Important**: Export the key to your environment to persist it across sessions.")
    # CRITICAL: Store this key securely - losing it means losing cached data
    # Persists the encryption key within the current configuration settings for the python session/REPL
    config_settings.set(env_var, encryption_pipeline_factory.secret_key)

    # Write the key to the default environment location. Use `create=True` to create a new .env file if it doesn't already exist.
    config_settings.write_key(env_var, create=True)

# Generates a new serializer from the factory
serializer = encryption_pipeline_factory()  # Create the `EncryptionPipelineFactory` and call it to generate an encryption serializer

# Creates a cached session with encryption — raising an error by default when an error occurs
session = CachedSessionManager.with_session(backend='sqlite', user_agent='scholar flux search', serializer=serializer, raise_on_error=True)

# Creates a basic response retrieval session to use as a part of a final search coordinator or separately
api = SearchAPI(query = 'encryption AND serialization', session = session)
```

### Alternative: Automatic Specification

When the secret key has been previously stored and read from a .env file or the `SCHOLAR_FLUX_CACHE_SECRET_KEY` environment variable, future sessions can reuse the key when `SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION` is enabled or `use_encryption=True` is specified:

```python

from scholar_flux.sessions import CachedSessionManager
from scholar_flux.api import SearchCoordinator

# For future sessions, simply specify use_encryption=True or set SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION for automatic encryption when a key is available.
session = CachedSessionManager.with_session(
    backend='sqlite',
    user_agent='scholar flux search',
    use_encryption=True,
    raise_on_error=True,
    verify_connection=True,  # Will raise an error for invalid tokens, serialization issues, bad directory specifications, etc.
)

# Create a SearchCoordinator that orchestrates the record retrieval and processing pipeline
coordinator = SearchCoordinator(query = 'cybersecurity best practices', session = session)
```

### Authentication with Redis or MongoDB

Both Redis and MongoDB Session and Response Cache storage backends each support the utilization of environment variables for authentication.

On initialization, connection credentials are read and masked via explicitly provided environment variables:

- `SCHOLAR_FLUX_REDIS_USERNAME`
- `SCHOLAR_FLUX_REDIS_PASSWORD`

- `SCHOLAR_FLUX_MONGODB_USERNAME`
- `SCHOLAR_FLUX_MONGODB_PASSWORD`

When available, these authentication parameters are automatically masked as secret strings, only unmasking at the time of request transmission:

```python
from scholar_flux import SearchCoordinator, CachedSessionManager, DataCacheManager, config_settings, masker

# Env variables automatically read as secret strings when available:
redis_has_auth = config_settings.get("SCHOLAR_FLUX_REDIS_USERNAME") and config_settings.get("SCHOLAR_FLUX_REDIS_PASSWORD")

# Layer 2 Response Cache: automatically reads host, port, and auth parameters
redis_cache_manager = DataCacheManager.with_storage("redis")

if redis_has_auth:
    print("Authentication parameters for Redis are available. These parameters are automatically applied on response cache initialization")
    # Configuration parameters are read as secrets when the environment variables contain valid values.
    assert masker.is_secret(redis_cache_manager.cache_storage.config.get("username"))
    assert masker.is_secret(redis_cache_manager.cache_storage.config.get("password"))

# When available, authentication parameters used automatically:
redis_cache_manager = DataCacheManager.with_storage("redis", verify_connection=True)


## When credentials are unnecessary for a session, remove the environment variables and restart, or unset them from the
## current configuration settings/OS environment for the session.
# config_settings.unset("SCHOLAR_FLUX_REDIS_USERNAME", unset_os_env=True)
# config_settings.unset("SCHOLAR_FLUX_REDIS_PASSWORD", unset_os_env=True)

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
