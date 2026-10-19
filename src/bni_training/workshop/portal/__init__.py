"""Shared Workshop Portal: one Streamlit Application for all ten groups (about 40 concurrent browsers).

Shared objects (registry, inference gate, read-only data tools) hold no group or user state. Everything a
user or group owns lives in a NamespacedState keyed by group_id and session_id, or in that session's own
output directory.
"""
