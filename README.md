# Agent Orchestrator

**Goal:** Run all development and orchestration on a **server** (Proxmox VMs/LXCs), while a **workstation** with an RTX 4070 Ti hosts the **GPU worker** (e.g., vLLM/OpenAI-compatible API). All developers (Win/Mac/Linux) enter through the **server**.

## High-level Architecture

- **Server stack (Proxmox VM/LXC):** API (FastAPI), router/agent, MCP servers, queue (Redis), reverse proxy (Caddy), observability (Prometheus, Grafana), and optional security (Fail2ban/CrowdSec), DNS/ad-blocker (Pi-hole/AdGuard) if desired.
- **Workstation (RTX 4070 Ti):** vLLM (or TGI) in Docker with `nvidia-container-toolkit`, exposed only to the server via LAN/mTLS.
- **Dev flow:** Remote dev via VS Code Dev Containers → CI builds → Deploy to server → Server routes inference to the GPU worker.

## Quickstart

### 0) Prerequisites
- Proxmox host ready; create a VM/LXC for `agent-server`.
- Docker + Compose on server and workstation.
- (Workstation) NVIDIA driver + `nvidia-container-toolkit`.

### 1) Configure environment
Copy `.env.example` to `.env` and fill values:
```bash
cp .env.example .env
```

### 2) Start server stack (control plane)

```bash
# local/dev
docker compose up -d

# server (uses overrides)
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

### 3) Start GPU worker on workstation

```bash
docker compose -f docker-compose.worker.yml up -d
```

### 4) Test

```bash
# From server: call the worker via gateway or direct vLLM
curl -s https://worker.local:8443/v1/models
```

### 5) Dev UX

* All devs SSH or VS Code Remote into the **server**.
* The server exposes a unified API. Internal services call the **worker** via OpenAI-compatible endpoints.
* MCP servers are configured in `mcp/config/mcp_servers.yaml`.

## Models & Sizing

* Default assumes models fit in **12 GB** (e.g., 7–13B, FP16 or low-bit). Use vLLM paged attention & quantization for longer contexts.
* When models outgrow 12 GB: consider quantized variants or re-evaluate GPU topology.

## MCP Hybrid Architecture

This system implements a hybrid MCP (Model Context Protocol) architecture:

| Dimension                    | Install **globally** on control plane                                                    | Install **per-repo** (in the project)                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Scope & reuse**            | Cross-project tools (GitHub, Jira, search, vector DB, secrets broker, artifact registry) | Repo-unique tools (custom code indexer, domain schema, one-off integrations) |
| **Versioning stability**     | You want **one version** for all teams; change managed by infra                          | The repo must **pin** exact versions compatible with its code/tooling        |
| **Security & secrets**       | Centralized secret custody, auditing, network ACLs                                       | Least-privilege, repo-scoped tokens, sandboxes per project                   |
| **Isolation / blast radius** | Lower isolation (shared process) unless namespaced                                       | High isolation; failures/updates affect only that repo                       |
| **Reproducibility / CI**     | Good for common infra; less deterministic per-repo without careful tagging               | Strong: repo contains its MCP stack → portable dev/CI                        |
| **Performance / caching**    | Shared caches (code search, embeddings) benefit all repos                                | Tailored indexes/caches per repo; no cross-pollution                         |
| **Ops overhead**             | Lower (one place to patch/observe)                                                       | Higher (N stacks), but automated with templates                              |

### Global MCP Servers (Control Plane)
- **GitHub MCP**: Repository operations, issue tracking, pull requests
- **Filesystem MCP**: File operations, code analysis, dependency tracking
- **Secrets MCP**: Secure secrets management with Vault integration
- **Vector DB MCP**: Embedding search, knowledge retrieval

### Per-Repo MCP Servers
- Custom code indexers
- Domain-specific schemas
- Project-unique integrations

## Observability

* Prometheus scrapes vLLM and system metrics.
* Grafana dashboards: `infra/observability/grafana/dashboards`.
* Comprehensive alerting for service health, performance, and resource usage.

## Security

* LAN allowlist, mTLS (Caddy), token auth for internal APIs.
* Optional WireGuard/Tailscale for remote laptops into the server.
* Vault integration for secrets management.

## Development Workflow

1. **Local Development**: Use VS Code Dev Containers for consistent environment
2. **Testing**: Comprehensive test suite with pytest, mypy, ruff, black
3. **CI/CD**: Automated testing, building, and deployment via GitHub Actions
4. **Deployment**: SSH-based deployment to server and worker nodes

## Proxmox Setup

See `deploy/server/provision_proxmox.md` for VM/LXC creation, cloud-init, and networking (VLANs, bridges).

## Makefile Commands

```bash
# Local development
make up              # Start local stack
make down            # Stop local stack
make logs            # View logs
make test-chat       # Test chat endpoint

# Server deployment
make up-server       # Start server stack
make logs-server     # View server logs

# Worker deployment
make up-worker       # Start GPU worker
make logs-worker     # View worker logs

# Testing
make test            # Run all tests
make lint            # Run linting
make type            # Run type checking
make fix             # Fix linting issues

# CI simulation
make ci              # Run full CI pipeline
```

## Project Structure

```
agent-orchestrator/
├── services/                    # Core services
│   ├── api/                    # FastAPI control plane
│   ├── router/                 # Agent router with MCP integration
│   ├── worker_client/          # vLLM/TGI client
│   ├── queue/                  # Redis configuration
│   └── gateway/                # Optional auth proxy
├── mcp/                        # MCP servers
│   ├── servers/                # Global and per-repo MCP servers
│   └── config/                 # MCP server configuration
├── infra/                      # Infrastructure configuration
│   ├── reverse-proxy/          # Caddy configuration
│   ├── networking/             # WireGuard, Tailscale
│   ├── observability/          # Prometheus, Grafana
│   └── security/               # Fail2ban, CrowdSec
├── worker/                     # GPU worker configuration
│   ├── vllm/                   # vLLM setup and docs
│   └── tgi/                    # TGI alternative
├── deploy/                     # Deployment scripts and guides
│   ├── server/                 # Proxmox provisioning
│   └── ci/                     # CI/CD scripts
└── dev/                        # Development tools
    ├── containers/             # Dev container configuration
    ├── scripts/                # Helper scripts
    └── docs/                   # Architecture and decisions
```

## Contributing

1. Install pre-commit hooks: `make install-pre-commit`
2. Follow the coding standards (ruff, black, mypy --strict)
3. Write tests for new functionality
4. Update documentation as needed
5. Submit pull requests with clear descriptions

## License

MIT License - see [LICENSE](LICENSE) for details.
