# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.




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