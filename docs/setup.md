# Developer Onboarding & Local Setup Guide

Follow this numbered guide to set up the TaskFlow API in a clean development environment.

## 1. Prerequisites
- **Node.js**: Version 18.x, 20.x, or 22.x LTS (`node --version`)
- **Git**: Installed and available in PATH (`git --version`)

## 2. Repository Setup
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd Knack_Labs
   ```
2. Verify directory layout:
   - `src/`: Application source code (controllers, models, services, utils)
   - `tests/`: Automated unit, integration, and security test suites
   - `docs/`: Technical specifications and ADRs

## 3. Dependency Installation
The TaskFlow API is built entirely on native Node.js standard modules (`node:crypto`, `node:events`, `node:test`, `node:assert/strict`) to minimize supply chain attack surface.
```bash
# Verify npm environment
npm --version
```

## 4. Environment Variables
Copy or verify `.env.example` (or rely on secure defaults):
- `PORT`: HTTP server listening port (Default: `3000`)
- `NODE_ENV`: Runtime environment (`development`, `test`, `production`)

## 5. Running Automated Verification
Execute the comprehensive test suite across all 54 unit, integration, RBAC, and capstone tests:
```bash
npm test
```
Expected output:
```
# tests 54
# pass 54
# fail 0
```

## 6. Starting the API Server
Start the local HTTP service:
```bash
node src/index.js
```
The server binds to `http://127.0.0.1:3000`. Health check endpoint:
```bash
curl -i http://localhost:3000/health
```
