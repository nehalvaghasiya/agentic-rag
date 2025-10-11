"""
Database initialization script for PGVector.

This script creates the necessary database schema and extensions for the RAG system.
Run this before first use if not using Docker (Docker auto-initializes).
"""

import asyncio
import os

import asyncpg
from loguru import logger

from rag.config import load_config, get_api_key


async def init_database():
    """
    Initialize PostgreSQL database with pgvector extension.

    This is async because:
    1. Database connections are I/O-bound
    2. Schema creation involves multiple SQL commands
    3. Non-blocking allows other operations to continue

    The script:
    1. Connects to PostgreSQL
    2. Creates pgvector extension
    3. Creates necessary tables for vector storage
    """
    # Load configuration
    config = load_config()

    # Get database credentials
    password = get_api_key(config.vectorstore.pgvector.password_env)
    db_config = config.vectorstore.pgvector

    # Build connection string
    dsn = (
        f"postgresql://{db_config.user}:{password}@"
        f"{db_config.host}:{db_config.port}/{db_config.database}"
    )

    logger.info(f"Connecting to PostgreSQL at {db_config.host}:{db_config.port}...")

    try:
        # Connect to database
        conn = await asyncpg.connect(dsn)

        # Create pgvector extension
        logger.info("Creating pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("✓ pgvector extension created")

        # The LangChain PGVector will create the collection table automatically
        # But we can verify the extension is working
        result = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        logger.info(f"✓ pgvector version: {result}")

        await conn.close()
        logger.info("✅ Database initialization completed successfully!")

        return True

    except Exception as e:
        logger.exception(f"❌ Error initializing database: {e}")
        raise


async def verify_database():
    """
    Verify that the database is properly configured.

    Returns:
        True if database is ready, False otherwise.
    """
    try:
        config = load_config()
        password = get_api_key(config.vectorstore.pgvector.password_env)
        db_config = config.vectorstore.pgvector

        dsn = (
            f"postgresql://{db_config.user}:{password}@"
            f"{db_config.host}:{db_config.port}/{db_config.database}"
        )

        conn = await asyncpg.connect(dsn)

        # Check if pgvector is installed
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');"
        )

        await conn.close()

        if result:
            logger.info("✅ Database is properly configured")
            return True
        else:
            logger.warning("⚠️ pgvector extension not found")
            return False

    except Exception as e:
        logger.error(f"❌ Error verifying database: {e}")
        return False


def main():
    """Main entry point for database initialization."""
    from rag.logging_config import setup_logging

    config = load_config()
    setup_logging(config)

    logger.info("=" * 60)
    logger.info("Database Initialization for Agentic RAG")
    logger.info("=" * 60)

    # Run async initialization
    success = asyncio.run(init_database())

    if success:
        # Verify
        is_ready = asyncio.run(verify_database())

        if is_ready:
            logger.info("\n✅ Database is ready for use!")
            logger.info("\nYou can now:")
            logger.info("  1. Start the backend: python -m rag.backend.app")
            logger.info("  2. Start the frontend: python -m rag.frontend.gradio_app")
            logger.info("  3. Or use Docker: docker-compose up -d")
        else:
            logger.error("\n❌ Database verification failed")
            exit(1)
    else:
        logger.error("\n❌ Database initialization failed")
        exit(1)


if __name__ == "__main__":
    main()
