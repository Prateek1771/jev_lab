import os

# Set before config/ is imported. load_dotenv never overrides a real env var,
# so a config/.env with real keys cannot switch tracing back on during tests.
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
