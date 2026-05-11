"""Reusable MCP prompts for Slurm batch scripts (BU SCC conventions)."""

from __future__ import annotations

import mcp.types as types

_PROMPT_ARG_COMMON = [
    types.PromptArgument(
        name="job_name",
        description="Slurm job name (-J); short alphanumeric + underscores.",
        required=False,
    ),
    types.PromptArgument(
        name="partition",
        description="Target partition (e.g. shared, interactive, gpu); verify against SCC docs.",
        required=False,
    ),
    types.PromptArgument(
        name="account",
        description="Slurm account / project string (#SBATCH -A).",
        required=False,
    ),
    types.PromptArgument(
        name="walltime",
        description="Wall time limit as HH:MM:SS for #SBATCH -t.",
        required=False,
    ),
    types.PromptArgument(
        name="modules",
        description="Space-separated module names to load (e.g. 'gcc/12 cuda').",
        required=False,
    ),
    types.PromptArgument(
        name="workdir",
        description="Working directory for the job (cd here before running commands).",
        required=False,
    ),
]


def list_prompt_definitions() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="write_batch_job",
            description="Draft a generic CPU Slurm batch script for BU SCC with #SBATCH headers and a sample body.",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="command",
                    description="Main command to run after modules load (e.g. python train.py).",
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="write_gpu_job",
            description="Draft a GPU Slurm batch script for BU SCC (GRES, partition, CUDA modules).",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="gpus_per_node",
                    description="GPUs per node for --gres=gpu:N (default 1).",
                    required=False,
                ),
                types.PromptArgument(
                    name="command",
                    description="Main GPU command (e.g. python train.py).",
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="write_job_array",
            description="Draft a Slurm job array script for BU SCC with %a/%A placeholders and per-task logic.",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="array_spec",
                    description="Array range for #SBATCH -a (e.g. 1-100%10).",
                    required=False,
                ),
                types.PromptArgument(
                    name="command",
                    description="Command template using SLURM_ARRAY_TASK_ID if needed.",
                    required=False,
                ),
            ],
        ),
    ]


def _arg(arguments: dict[str, str] | None, key: str, default: str) -> str:
    if not arguments:
        return default
    val = arguments.get(key)
    return default if val in (None, "") else val


def get_prompt_result(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    job_name = _arg(arguments, "job_name", "my_job")
    partition = _arg(arguments, "partition", "shared")
    account = _arg(arguments, "account", "<BU_SCC_PROJECT>")
    walltime = _arg(arguments, "walltime", "01:00:00")
    modules = _arg(arguments, "modules", "gcc")
    workdir = _arg(arguments, "workdir", "$SLURM_SUBMIT_DIR")
    command = _arg(arguments, "command", "echo 'Replace with your workload'")

    if name == "write_batch_job":
        text = _generic_batch_text(
            job_name=job_name,
            partition=partition,
            account=account,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            command=command,
        )
        return types.GetPromptResult(
            description="Generic CPU batch job for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    if name == "write_gpu_job":
        gpus = _arg(arguments, "gpus_per_node", "1")
        text = _gpu_batch_text(
            job_name=job_name,
            partition=partition,
            account=account,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            gpus_per_node=gpus,
            command=command,
        )
        return types.GetPromptResult(
            description="GPU batch job for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    if name == "write_job_array":
        array_spec = _arg(arguments, "array_spec", "1-10%4")
        text = _array_batch_text(
            job_name=job_name,
            partition=partition,
            account=account,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            array_spec=array_spec,
            command=command,
        )
        return types.GetPromptResult(
            description="Slurm job array for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    raise ValueError(f"Unknown prompt: {name}")


def _generic_batch_text(
    *,
    job_name: str,
    partition: str,
    account: str,
    walltime: str,
    modules: str,
    workdir: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load ..."
    return f"""You are helping a user run work on the Boston University Shared Computing Cluster (SCC).

Write a **complete, ready-to-submit Slurm batch script** for a **CPU-only** job.

Requirements:
- Use `#!/bin/bash` shebang.
- Include standard `#SBATCH` directives: job name (-J), partition (-p), account (-A), walltime (-t), nodes/cores appropriate for SCC (start with 1 node, 4–8 tasks/cores unless the user implied otherwise).
- Load modules with `module purge` then explicit `module load` lines.
- `cd` to the requested working directory (use this value: {workdir}).
- Use `srun` for the main parallel step when running MPI or multi-task programs; otherwise plain shell is fine for a single-process script.
- Add brief comments explaining each `#SBATCH` line.
- Do **not** invent live cluster limits; mention the user should confirm partition/account with `sacctmgr` / SCC docs / `module avail`.

Context from prompt arguments (substitute sensibly, keep placeholders if still unknown):
- job_name: {job_name}
- partition: {partition}
- account: {account}
- walltime: {walltime}
- modules (space-separated input, expand each): {modules}
- command to run: {command}

Example module block shape (replace with user's modules):
{mod_lines}

Output **only** the batch script, no surrounding markdown fences unless the host requires it.
"""


def _gpu_batch_text(
    *,
    job_name: str,
    partition: str,
    account: str,
    walltime: str,
    modules: str,
    workdir: str,
    gpus_per_node: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load cuda/... cudnn/..."
    return f"""You are helping a user run **GPU** work on BU SCC.

Write a **complete Slurm batch script** that requests GPUs correctly for SCC.

Requirements:
- `#!/bin/bash`
- `#SBATCH` directives including: job name, partition (often a GPU partition — user hint: {partition}), account, walltime, cpus-per-task, mem, and **GPU GRES** (e.g. `#SBATCH --gres=gpu:{gpus_per_node}` — use {gpus_per_node} unless inconsistent with the user's request).
- Load CUDA/cudnn or framework modules; use `module purge` first.
- `cd` to {workdir}
- Prefer `srun` for the GPU launch line when using MPI+GPU patterns; for single-node deep learning, calling the command after `module load` is acceptable if commented.
- Remind briefly to check `nvidia-smi` inside an interactive session if debugging drivers.

Arguments:
- job_name: {job_name}
- partition: {partition}
- account: {account}
- walltime: {walltime}
- modules: {modules}
- gpus_per_node: {gpus_per_node}
- command: {command}

Module block shape:
{mod_lines}

Output **only** the batch script.
"""


def _array_batch_text(
    *,
    job_name: str,
    partition: str,
    account: str,
    walltime: str,
    modules: str,
    workdir: str,
    array_spec: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load ..."
    return f"""You are helping a user run a **Slurm job array** on BU SCC.

Write a **complete batch script** using `#SBATCH -a {array_spec}` (adjust only if clearly wrong).

Requirements:
- `#!/bin/bash`
- Standard `#SBATCH` lines plus array concurrency/throttle as implied by the array spec.
- Use `$SLURM_ARRAY_TASK_ID`, `%a`, and `%A` in output filenames (e.g. `#SBATCH -o logs/job_%A_%a.out`).
- `cd` to {workdir}
- Show a minimal pattern to map task id → input file or parameter (case statement or file list) **as a commented example** the user can adapt.
- `module purge` then loads:
{mod_lines}
- User command template / intent: {command}

Other arguments:
- job_name: {job_name}
- partition: {partition}
- account: {account}
- walltime: {walltime}

Output **only** the batch script.
"""
