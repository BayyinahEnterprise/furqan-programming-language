# Security policy

## Supported versions

The latest tagged release on `main` is the supported version. Older tags
are kept for reproducibility of cited results and are not patched.

| Version              | Supported |
|----------------------|-----------|
| Latest minor on main | yes       |
| All earlier versions | no        |

## Reporting a vulnerability

Send a private report to **bayyinahenterprises@tuta.com**.

Please include:

- the affected surface (this repository, the `tryfurqan.com` demo backend,
  or the Bayyinah scanner);
- a minimal reproducer (a `.fqn` source, a curl invocation, or a Python
  snippet that triggers the issue);
- the observed behaviour and the behaviour you expected;
- the version, commit SHA, or live URL you tested against.

Please do **not** open a public GitHub issue for vulnerabilities. We will
acknowledge receipt within five business days, share an initial assessment
within ten business days, and coordinate disclosure with you before any
public write-up.

## Scope

In scope:

- the type-checker (parser, checker modules, error envelopes);
- the CLI (`furqan check`, `furqan version`);
- the `tryfurqan.com/demo` backend, including method gating, input caps,
  fixture lookup, and rate limiting.

Out of scope:

- attacks that require a compromised local machine to deliver a malicious
  `.fqn` file the user is already going to compile;
- denial-of-service that requires sustained traffic above the rate limits
  documented on the demo page;
- third-party services we link to (Zenodo, GitHub, Buttondown).

## Coordinated disclosure

We aim for a 90-day private window from acknowledgement to public
disclosure. If a fix lands earlier, the public note can land earlier; if
the issue requires more coordination, we will agree on an extended
window with the reporter before any public disclosure.

## Acknowledgements

Reporters who follow this policy are listed in `CHANGELOG.md` against the
release that fixes the issue, with their preferred attribution (real
name, handle, or anonymous).
