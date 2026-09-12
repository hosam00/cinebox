# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Email the maintainer directly:

- **Hossam Gamal** — `hosamgamal33345@gmail.com`

You can expect an acknowledgement within a few days and a coordinated fix
before any public disclosure.

## Scope

This project scrapes publicly exposed web endpoints and passes URLs to local
players. Report anything that:

- executes untrusted code,
- leaks credentials or personal data,
- exfiltrates data from a user's machine,
- lets an attacker inject commands via title/stream/metadata strings.

Best-effort resolution means providers are community-maintained pages; a
compromised provider could serve malicious content — such dependency issues
are treated as in-scope security bugs too.