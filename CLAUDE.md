# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Getting Started and Development Commands

The project utilizes a mix of npm scripts for frontend development and `make` targets within the `dify/Makefile` for core services and testing.

### Core Build & Test Targets
These commands, primarily located in `dify/Makefile`, should be used for full system builds and tests:
*   **Development Server:** `make dev` (Starts a local development environment).
*   **Full Build:** `make build` (Compiles all necessary services and assets for deployment).
*   **Testing Suite:** `make test` (Runs comprehensive unit, integration, and end-to-end tests across the stack).
*   **Linting:** `make lint` (Enforces coding standards across all modules).
*   **Database Setup:** `make migrate-dev` (Handles development database migrations).

### Frontend Specific Targets
The frontend structure within `dify/package.json` uses standard npm scripts:
*   `npm run dev`: Starts the Vite development server.
*   `npm run build`: Creates production-ready static assets via Vite.
*   `npm run lint`: Runs ESLint checks on JavaScript and TypeScript files.

## 📐 High-Level Architecture

The platform adopts a modular, orchestration-based architecture centered around the `dify/api` core services. The overall system is designed to be highly extensible for new features while maintaining strong data contracts.

### Core Components:
1.  **API Core (`dify/api`):** This module is the central nervous system. It handles workflow execution, prompt template orchestration, and provides standardized APIs that govern how services interact. Key logic resides in `dify/api/core`, especially schema validation (e.g., within `dify/api/core/schemas`) and workflow graph management.
2.  **Web Frontend (`dify/web`):** Responsible for the user interface, utilizing a component-based pattern throughout its structure (`dify/web/app/components`). It is built to consume the standardized APIs provided by the core backend.
3.  **SDKs & Interoperability (`dify/sdks`):** Client libraries (e.g., `nodejs-client`, `php-client`) are maintained here, ensuring external services can reliably interact with the platform's APIs using idiomatic language bindings.

### Architectural Patterns:
*   **Workflow Orchestration:** The system is designed to manage complex state transitions and task flows (see `dify/api/tests/unit_tests/core/workflow/graph_engine`). This engine coordinates multiple steps, making the core logic highly dependent on clear data inputs defined by schemas.
*   **Schema-Driven Contracts:** Strong data contracts are enforced using JSON schema definitions throughout the system. When developing or modifying API endpoints, always refer to existing schema files (e.g., `*.json` in `dify/api/core/schemas`) to maintain consistency between frontend consumption and backend expectations.
*   **Internationalization (i18n):** The presence of localized documentation and resources within the `dify/docs` directory indicates a strong commitment to multilingual support; new features must be evaluated for global compatibility from the outset.

## 📜 Existing Development Guidelines & Rules
*There are no explicit rules found in `.cursor/rules/` or `.github/copilot-instructions.md`. If external guidelines emerge, they should be documented here.*

## ✨ Next Steps For Developers
1.  **For API development:** Focus on the `dify/api/core` layer and adhere strictly to existing schemas.
2.  **For UI development:** Consume APIs via defined endpoints, leveraging component structure within `dify/web`.
3.  **When starting new work:** Begin by running `make dev` and consulting relevant components in `dify/api/core` for best practices regarding data handling and state management.