"""Called in place of claude for a no-network launcher inspection."""
import json
import os
import sys
from urllib.parse import urlparse

args = sys.argv[1:]
models = []
agents = {}
for n, value in enumerate(args):
    if value == "--model":
        models.append(args[n + 1])
    elif value.startswith("--model="):
        models.append(value.split("=", 1)[1])
    if value == "--agents":
        definitions = json.loads(args[n + 1])
        agents = {k: {"model": v.get("model"), "tools": v.get("tools")} for k, v in definitions.items()}
print(json.dumps({"probe": True, "provider_host": urlparse(os.environ.get("ANTHROPIC_BASE_URL", "")).hostname,
                  "main_model_options": models, "agents": agents,
                  "has_visual_rules": "--append-system-prompt" in args,
                  "haiku_alias": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
                  "subagent_default": os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL")}, ensure_ascii=False))
