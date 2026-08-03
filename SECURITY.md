# Security Policy

## Reporting a Vulnerability

**Please do not open a public GitHub issue for a security vulnerability.** That publishes the details before a fix exists.

Instead, use GitHub's private reporting: go to the [Security tab](https://github.com/xDarkzx/Audacity-MCP/security) → **Report a vulnerability**. This opens a private conversation only you and the maintainer can see, and lets you attach details/reproduction steps without exposing them publicly.

## What to Expect

This is a solo-maintained project, so response times aren't guaranteed on a fixed SLA, but a genuine security report will be prioritized ahead of regular feature work. You'll get an acknowledgement, and a fix (or an explanation if it turns out not to be exploitable) once it's been looked into.

## Scope

AudacityMCP runs locally and talks to Audacity over a named pipe on your own machine — there's no server, no cloud component, and no network exposure by design. Relevant reports include things like:

- A way for a malicious audio file, project file, or MCP tool call to trigger unintended file access, code execution, or data exfiltration
- Path traversal or injection through any tool parameter
- Anything that lets an MCP client do more than the documented tools allow

Reports about the underlying Audacity application itself belong with the [Audacity project](https://github.com/audacity/audacity), not here.

## Supported Versions

Only the latest published version is supported. Please update (`pip install --upgrade audacity-mcp-server`) before reporting, in case it's already fixed.
