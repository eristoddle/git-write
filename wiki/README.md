# GitWrite Wiki

Welcome to the comprehensive GitWrite documentation! This wiki provides detailed information about the GitWrite platform - a version control system designed specifically for writers and writing teams.

## 📖 What is GitWrite?

GitWrite is a version control platform that leverages Git's robust infrastructure while abstracting its complexity for non-technical users. It transforms developer-centric Git terminology into writer-friendly concepts, making version control accessible to authors, editors, beta readers, and publishers.

### Key Value Propositions
- **Writer-Friendly Interface**: "Save" instead of "commit", "explorations" instead of "branches"
- **Collaborative Workflows**: Structured feedback integration between authors, editors, and beta readers
- **Full Git Compatibility**: Works with existing Git repositories and hosting services
- **Multiple Interfaces**: CLI, Web UI, Mobile app, and API access
- **Export Capabilities**: Generate EPUB, PDF, DOCX via Pandoc integration

## 🏗️ Architecture Overview

GitWrite follows a layered, multi-component architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Reader  │    │  Writing Tools  │
│   (React/TS)    │    │ (React Native)  │    │   (3rd Party)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │    TypeScript SDK     │
                     │   (npm package)       │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │      REST API         │
                     │   (FastAPI/Python)    │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │    GitWrite CLI       │
                     │   (Python Click)      │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │       Git Core        │
                     │   (libgit2/pygit2)    │
                     └───────────────────────┘
```

## 📚 Documentation Structure

### 🎯 System Overview
- [System Overview](system-overview/README.md) - High-level system description
- [Key Features](system-overview/key-features.md) - Core platform capabilities
- [User Workflows](system-overview/user-workflows.md) - Common usage patterns
- [Technology Stack](system-overview/technology-stack.md) - Technical foundation
- [Getting Started](system-overview/getting-started.md) - Quick start guide

### 🏛️ Core Architecture
- [Layered Architecture](core-architecture/layered-architecture.md) - System design patterns
- [Facade Pattern](core-architecture/facade-pattern.md) - Complexity abstraction
- [Adapter Pattern](core-architecture/adapter-pattern.md) - Writer-centric abstractions
- [API Gateway](core-architecture/api-gateway.md) - FastAPI implementation
- [Technology Trade-offs](core-architecture/technology-tradeoffs.md) - Design decisions
- [Cross-Cutting Concerns](core-architecture/cross-cutting-concerns.md) - Shared system aspects

### ⚙️ Core Engine (Python Library)
- [Repository Management](core-engine/repository-management.md) - Git repo operations
- [Versioning System](core-engine/versioning-system.md) - Change tracking
- [Branching System](core-engine/branching-system.md) - Exploration management
- [Annotation System](core-engine/annotation-system.md) - Feedback and comments
- [Export Functionality](core-engine/export-functionality.md) - Document generation
- [Tagging System](core-engine/tagging-system.md) - Version labeling
- [Error Handling](core-engine/error-handling.md) - Exception management

### 🌐 Backend API (FastAPI)
- [Authentication](backend-api/authentication.md) - Security and access control
- [Repository Operations](backend-api/repository-operations.md) - Git API endpoints
- [File Uploads](backend-api/file-uploads.md) - Content management
- [Annotations](backend-api/annotations.md) - Feedback API

### 🎨 Frontend Application (React/TypeScript)
- [Component Architecture](frontend-app/component-architecture.md) - UI structure
- [Routing & Navigation](frontend-app/routing-navigation.md) - Page flow
- [State Management](frontend-app/state-management.md) - Data handling
- [API Integration](frontend-app/api-integration.md) - Backend communication
- [Word Diff Visualization](frontend-app/word-diff-visualization.md) - Change display

### 💻 CLI Tool (Python Click)
- [Command Reference](cli-tool/command-reference.md) - Available commands
- [Configuration Management](cli-tool/configuration-management.md) - Settings and preferences
- [Common Workflows](cli-tool/common-workflows.md) - Typical usage patterns
- [Extending the CLI](cli-tool/extending-cli.md) - Plugin development

### 📦 TypeScript SDK
- [API Client](typescript-sdk/api-client.md) - HTTP client implementation
- [Type Definitions](typescript-sdk/type-definitions.md) - TypeScript interfaces
- [Installation and Usage](typescript-sdk/installation-usage.md) - Getting started
- [Testing and Integration](typescript-sdk/testing-integration.md) - Development support

### 🧪 Testing Strategy
- [API Testing](testing-strategy/api-testing.md) - Backend test approaches
- [Core Module Testing](testing-strategy/core-module-testing.md) - Business logic tests
- [CLI Testing](testing-strategy/cli-testing.md) - Command-line interface tests
- [Test Infrastructure](testing-strategy/test-infrastructure.md) - Testing tools and setup

### 🚀 Deployment & Configuration
- [Development Setup](deployment-config/development-setup.md) - Local environment
- [Production Deployment](deployment-config/production-deployment.md) - Live environment
- [Configuration Management](deployment-config/configuration-management.md) - Settings
- [Scaling and Performance](deployment-config/scaling-performance.md) - Optimization
- [Backup and Recovery](deployment-config/backup-recovery.md) - Data protection

### 👥 User Guides
- [Getting Started](user-guides/getting-started.md) - First steps with GitWrite
- [Collaborative Writing](user-guides/collaborative-writing.md) - Team workflows
- [Editorial Review](user-guides/editorial-review.md) - Editor processes
- [Beta Reader Integration](user-guides/beta-reader-integration.md) - Feedback collection
- [Troubleshooting](user-guides/troubleshooting.md) - Common issues and solutions

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on contributing to GitWrite.

## 📄 License

This project is licensed under the terms specified in the main repository.

---

*This wiki is generated from the project's comprehensive documentation system and is regularly updated to reflect the latest features and architectural decisions.*