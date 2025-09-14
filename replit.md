# AI Trading System - MCP Architecture

## Overview

This is an AI-powered automated trading system built on a Multi-Agent Cooperation Platform (MCP) architecture. The system implements a microservices design pattern with event-driven communication between specialized AI agents for market analysis, risk management, order execution, and portfolio monitoring. The core system focuses on cryptocurrency trading through OKX exchange integration, featuring real-time data processing, technical indicator calculation, and automated decision-making capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

### September 14, 2025 - Major Data Management Redesign
- **Short Filename System**: Changed from complex timestamped filenames to simple format (1m.csv, 5m.csv, 1h.csv, 2h.csv, etc.)
- **Data Overwrite Mode**: System now overwrites previous K-line data instead of creating new files each run
- **Automatic Cleanup**: Implemented cleanup logic to remove timeframes not fetched in current run
- **MCP Compatibility Maintained**: Updated manifest system to work with new filename structure
- **File Corruption Fix**: Resolved corrupted enhanced_data_manager.py and rewrote with clean architecture

## System Architecture

### Core Architecture Pattern
The system follows an event-driven microservices architecture with the following key components:

- **API Gateway**: Central entry point for external requests and task distribution
- **Message Queue**: Communication hub for asynchronous inter-agent messaging (RabbitMQ/Redis Pub/Sub)
- **Multi-Agent System**: Specialized AI agents for different trading functions
- **Database Layer**: Persistent storage for trade logs, configuration, and system state
- **MCP Service**: Local data access service with FastAPI for AI agents

### Agent Architecture
The system implements multiple specialized agents:

1. **Analysis Agent**: Market analysis and trading signal generation using LLM with tool-calling capabilities
2. **Risk Management Agent**: Trade validation and risk assessment
3. **Execution Agent**: Order placement and trade execution
4. **Monitoring Agent**: Real-time position and trigger management
5. **Review Agent**: Post-trade analysis and learning summary generation

### Data Management Architecture
- **Enhanced Data Manager**: Centralized data fetching and processing from OKX API
- **Technical Indicator Engine**: Real-time calculation of trading indicators (RSI, MACD, Bollinger Bands, etc.)
- **File-based Storage**: CSV/Parquet format for historical data with manifest-based access control
- **Configuration Management**: YAML-based configuration system for trading parameters

### Security Architecture
- **API Key Management**: Environment variable-based credential storage
- **Access Control**: Manifest-based file authorization system
- **Audit Trail**: Comprehensive logging of all data access and trading activities
- **Atomic Operations**: Safe file operations with temporary file patterns

### Communication Flow
The system uses publish-subscribe messaging patterns:
- Agents communicate through message queues without direct coupling
- Event-driven triggers for analysis, execution, and monitoring
- JSON message format for standardized inter-agent communication

## External Dependencies

### Trading APIs
- **OKX API**: Primary cryptocurrency exchange integration for market data, account management, and order execution
- **OKX WebSocket**: Real-time market data streaming

### Data Processing Libraries
- **pandas**: Data manipulation and time series analysis
- **ta (Technical Analysis)**: Technical indicator calculations
- **numpy**: Numerical computations for custom indicators

### Web Framework
- **FastAPI**: MCP service API implementation with automatic documentation
- **Pydantic**: Data validation and serialization
- **uvicorn**: ASGI server for FastAPI applications

### Configuration and Environment
- **python-dotenv**: Environment variable management for API credentials
- **PyYAML**: Configuration file parsing and management

### Logging and Monitoring
- **Python logging**: Comprehensive logging with rotating file handlers
- **requests**: HTTP client with retry strategies for API reliability

### Message Queue (Planned)
- **RabbitMQ/Redis**: Inter-agent communication infrastructure (architecture ready, implementation pending)

### Database (Planned)
- **PostgreSQL/SQLite**: Persistent storage for trade logs and system state (architecture ready, may be added later)