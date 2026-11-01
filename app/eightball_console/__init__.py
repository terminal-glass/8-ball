"""8-Ball standalone console: a small local web console for a host's Ollama models.

Generic and self-contained: it reads the public 8-Ball catalog (profiles/, data/normalized/,
config/) and a host profile snapshot, talks only to configured Ollama instances through the
native Ollama REST API, and runs model jobs in a durable background runner.
"""
__version__ = "0.1.0"
