# Blender MCP setup (drive `buoy_sim/` with natural language)

This connects a running Blender to an AI client (Claude Desktop / Cursor / Claude
Code CLI) via [blender-mcp](https://github.com/ahujasid/blender-mcp), so you can
say *"run the buoy generator for Sea State 3"* and have it execute the scripts in
this folder live inside Blender.

## Where each piece runs

Everything below runs on **your own machine**, next to your Blender. blender-mcp
pairs a Blender addon (a socket server on `localhost:9876`) with an MCP server
your AI client launches; the client talks to the addon. A cloud/remote agent
cannot reach your local Blender — this is a local setup.

## Prerequisites (verified)

- **Blender 3.0+** — the addon's `bl_info` requires `(3, 0, 0)`.
- **uv** package manager (provides `uvx`). Install with the official installer,
  not `pip install uv`:
  - macOS: `brew install uv`
  - Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` (open a new shell)
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- No manual clone needed: `uvx blender-mcp` fetches the published package. The
  only file you take from the repo is `addon.py`.

> Smoke-tested in a clean environment: `uvx --python 3.11 blender-mcp` resolves
> and installs its 37 dependencies and imports without error. Pinning `3.11`
> (still satisfies the package's `requires-python >=3.10`) plus
> `UV_PYTHON_PREFERENCE=only-managed` avoids conda/pyenv/asdf picking a bad
> interpreter.

## 1. Register the MCP server with your client

Ready-to-merge config: [`mcp/blender.mcp.json`](mcp/blender.mcp.json). Merge the
`blender` entry into your client's `mcpServers` block (don't clobber other
servers).

**Claude Code CLI** — one command:
```bash
claude mcp add blender uvx --python 3.11 blender-mcp
```

**Claude Desktop** — Settings → Developer → Edit Config → `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["--python", "3.11", "blender-mcp"],
      "env": { "UV_PYTHON_PREFERENCE": "only-managed" }
    }
  }
}
```

**Cursor** — Settings → MCP (global), or a project `.cursor/mcp.json`, same block.
On Windows, if `spawn uvx ENOENT` appears, wrap it: `"command": "cmd", "args":
["/c", "uvx", "--python", "3.11", "blender-mcp"]`, then fully quit and relaunch
the client (GUI clients don't inherit your terminal PATH).

> Run only **one** MCP server instance (Desktop *or* Cursor, not both).

## 2. Install the Blender addon

1. Download `addon.py` from the [blender-mcp repo](https://github.com/ahujasid/blender-mcp)
   (or its [releases](https://github.com/ahujasid/blender-mcp/releases)).
2. Blender → Edit → Preferences → Add-ons → **Install…** → select `addon.py`.
3. Enable the checkbox next to **"Interface: Blender MCP"**.

> Note: the addon can execute arbitrary Python inside Blender on request. That's
> the whole point (it's how the buoy scripts run), but it's the trust model —
> only connect a client you control.

## 3. Connect

1. In Blender's 3D viewport press **N** to open the sidebar.
2. Open the **BlenderMCP** tab → click **Connect to Claude**.
3. Make sure your client shows the `blender` server connected (the tools/hammer
   icon appears). Default connection is `localhost:9876`
   (`BLENDER_HOST` / `BLENDER_PORT` override it).

## 4. Drive `buoy_sim/` from natural language

Once connected, the client has an `execute_blender_code` tool. Point it at this
folder and ask, e.g.:

> Run `buoy_sim/main.py`'s pipeline for Sea State 3 with Hs 1.8 m and Tp 7 s,
> anchored mooring, chase camera, 30 s.

or have it paste the module calls directly:

```python
import sys; sys.path.append(r"/absolute/path/to/buoy_sim")
import config, buoy_generator, ocean_generator, mooring_generator, hydrodynamics
from mathutils import Vector
cfg = config.SimConfig(sea=config.sea_state(3, hs=1.8, tp=7.0))
ocean = ocean_generator.build(cfg.sea, cfg.scene)
buoy  = buoy_generator.build(cfg.buoy)
moor  = mooring_generator.build(cfg.mooring, Vector((0,0,0)))
log   = hydrodynamics.simulate(buoy, cfg.buoy, cfg.sea, cfg.scene, moor, ocean)
print(log.stats())
```

The same scripts also run headless without MCP:
`blender --background --python buoy_sim/main.py -- --sea 3 --hs 1.8 --tp 7.0`.
