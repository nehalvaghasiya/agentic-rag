"""
Document loaders package.

Provides interfaces and implementations for loading documents from various sources.
Each loader follows the Interface Segregation Principle, implementing only the
necessary functionality for its document type.

All loaders are async-capable for I/O-bound operations (file reading, HTTP requests).
"""
