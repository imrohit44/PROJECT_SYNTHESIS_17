"""Service packages (banking API + fraud service) share the ``services`` namespace.

``services/common`` holds observability and tracing helpers imported by both
services. Marking ``services`` as a package keeps mypy's module resolution
single-rooted (see "Source file found twice" guidance).
"""
