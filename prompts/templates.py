"""Reusable MCP prompts for SGE / qsub batch scripts (BU SCC TechWeb conventions)."""

from __future__ import annotations

import mcp.types as types

_PROMPT_ARG_COMMON = [
    types.PromptArgument(
        name="job_name",
        description="SGE job name for #$ -N (short alphanumeric + underscores).",
        required=False,
    ),
    types.PromptArgument(
        name="project",
        description="SCC project for #$ -P (same string you use with qsub).",
        required=False,
    ),
    types.PromptArgument(
        name="queue",
        description="Optional queue name for #$ -q (buy-in or GPU queues when you know the name).",
        required=False,
    ),
    types.PromptArgument(
        name="walltime",
        description="Hard wall clock limit hh:mm:ss for #$ -l h_rt=… (default 12:00:00 in many examples).",
        required=False,
    ),
    types.PromptArgument(
        name="modules",
        description="Space-separated module names to load after module purge.",
        required=False,
    ),
    types.PromptArgument(
        name="workdir",
        description="Directory to cd into before running commands (optional; default stays in submit dir).",
        required=False,
    ),
]


def _project(arguments: dict[str, str] | None) -> str:
    """SCC project: prefer `project`, fall back to legacy `account` key."""
    if not arguments:
        return "<SCC_PROJECT>"
    p = arguments.get("project") or arguments.get("account")
    return "<SCC_PROJECT>" if p in (None, "") else p


def list_prompt_definitions() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="write_batch_job",
            description="Draft a generic CPU-oriented SGE qsub script for BU SCC (#$, -P, h_rt, optional -pe omp).",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="pe_omp_slots",
                    description="If set, add #$ -pe omp N for shared-memory / threaded jobs (e.g. 8).",
                    required=False,
                ),
                types.PromptArgument(
                    name="command",
                    description="Commands to run after modules (e.g. python myscript.py).",
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="write_gpu_job",
            description="Draft an SGE GPU qsub script for BU SCC (-pe omp, -l gpus=, -l gpu_c=, modules).",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="cpu_slots",
                    description="CPU slots for #$ -pe omp N (e.g. 4) alongside GPUs.",
                    required=False,
                ),
                types.PromptArgument(
                    name="gpus",
                    description="Number of GPUs for #$ -l gpus=N (e.g. 1).",
                    required=False,
                ),
                types.PromptArgument(
                    name="gpu_c",
                    description="Minimum GPU compute capability for #$ -l gpu_c=… (e.g. 7.0).",
                    required=False,
                ),
                types.PromptArgument(
                    name="command",
                    description="Main GPU workload (e.g. python my_pytorch_prog.py).",
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="write_job_array",
            description="Draft an SGE array job script (#$ -t range, SGE_TASK_ID, NSLOTS patterns).",
            arguments=_PROMPT_ARG_COMMON
            + [
                types.PromptArgument(
                    name="array_range",
                    description="Array range for #$ -t (e.g. 1-100 or 1-3).",
                    required=False,
                ),
                types.PromptArgument(
                    name="command",
                    description="Per-task command using SGE_TASK_ID or file-index pattern.",
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
    job_name = _arg(arguments, "job_name", "myjob")
    project = _project(arguments)
    queue = _arg(arguments, "queue", "")
    walltime = _arg(arguments, "walltime", "12:00:00")
    modules = _arg(arguments, "modules", "python3/3.13.8")
    workdir = _arg(arguments, "workdir", "")
    command = _arg(arguments, "command", "python -V")

    if name == "write_batch_job":
        pe_omp = _arg(arguments, "pe_omp_slots", "")
        text = _generic_batch_text(
            job_name=job_name,
            project=project,
            queue=queue,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            pe_omp_slots=pe_omp,
            command=command,
        )
        return types.GetPromptResult(
            description="Generic SGE / qsub CPU batch script for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    if name == "write_gpu_job":
        cpus = _arg(arguments, "cpu_slots", "4")
        gpus = _arg(arguments, "gpus", "1")
        gpu_c = _arg(arguments, "gpu_c", "7.0")
        text = _gpu_batch_text(
            job_name=job_name,
            project=project,
            queue=queue,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            cpu_slots=cpus,
            gpus=gpus,
            gpu_c=gpu_c,
            command=command,
        )
        return types.GetPromptResult(
            description="SGE GPU qsub script for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    if name == "write_job_array":
        array_range = _arg(arguments, "array_range", _arg(arguments, "array_spec", "1-10"))
        text = _array_batch_text(
            job_name=job_name,
            project=project,
            queue=queue,
            walltime=walltime,
            modules=modules,
            workdir=workdir,
            array_range=array_range,
            command=command,
        )
        return types.GetPromptResult(
            description="SGE array job (qsub) for BU SCC",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(type="text", text=text),
                )
            ],
        )
    raise ValueError(f"Unknown prompt: {name}")


def _queue_lines(queue: str) -> str:
    if not queue.strip():
        return "# (optional) #$ -q specific_queue_name"
    return f"#$ -q {queue}"


def _cd_block(workdir: str) -> str:
    if not workdir.strip():
        return "# Job starts in the submission directory by default."
    return f"cd {workdir}"


def _generic_batch_text(
    *,
    job_name: str,
    project: str,
    queue: str,
    walltime: str,
    modules: str,
    workdir: str,
    pe_omp_slots: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load ..."
    pe_block = (
        f"#$ -pe omp {pe_omp_slots}\nexport OMP_NUM_THREADS=$NSLOTS"
        if pe_omp_slots.strip()
        else "# (optional) #$ -pe omp N   # then: export OMP_NUM_THREADS=$NSLOTS"
    )
    return f"""You are helping a user run work on the Boston University Shared Computing Cluster (SCC).

Write a **complete, ready-to-submit Sun Grid Engine (SGE) batch script** for **qsub** on SCC.

Hard requirements from BU TechWeb documentation:
- Shebang **must** be `#!/bin/bash -l` whenever the script uses **module**.
- Use **#$** lines for qsub directives (NOT #SBATCH).
- Include **#$ -P** with the SCC project: {project}
- Include **#$ -l h_rt={walltime}** (hard wall clock limit).
- Include **#$ -N {job_name}** and commonly **#$ -j y** to merge stdout/stderr unless the user needs separate files.
- Optional queue selection:
{_queue_lines(queue)}
- Parallel / threaded section (omit or adjust if this is strictly single-slot):
{pe_block}
- `module purge` then loads:
{mod_lines}
- Working directory:
{_cd_block(workdir)}
- User’s main command(s):
{command}

Remind the user to:
- End the script with a blank line if their workflow requires it (per TechWeb “Submitting your Batch Job”).
- Pick **-pe omp** slot counts from the recommended set (1,2,3,4,8,16,28,32,36) when possible.
- Verify limits (runtime, memory, PE) with ingested TechWeb via **search_docs** or **help@scc.bu.edu**.

Output **only** the shell script (no markdown fences).
"""


def _gpu_batch_text(
    *,
    job_name: str,
    project: str,
    queue: str,
    walltime: str,
    modules: str,
    workdir: str,
    cpu_slots: str,
    gpus: str,
    gpu_c: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load miniconda / academic-ml / ..."
    return f"""You are helping a user run a **GPU job** on BU SCC using **qsub** and SGE resource requests.

Write a **complete batch script** following TechWeb “Batch Script Examples” (GPU section) and GPU computing pages.

Requirements:
- `#!/bin/bash -l`
- **#$ -P {project}**
- **#$ -l h_rt={walltime}**
- **#$ -N {job_name}**
- Request CPUs with **#$ -pe omp {cpu_slots}** (example pattern from SCC GPU samples).
- Request GPUs with **#$ -l gpus={gpus}** and capability **#$ -l gpu_c={gpu_c}** (capability is a *minimum*; the scheduler may assign newer GPUs).
- Optional queue line:
{_queue_lines(queue)}
- `module purge` then the user’s stack, e.g.:
{mod_lines}
- Working directory:
{_cd_block(workdir)}
- Main command:
{command}

Mention **qgpus** / **qgpus -v** on SCC for live GPU inventory and queue mapping.

Output **only** the shell script.
"""


def _array_batch_text(
    *,
    job_name: str,
    project: str,
    queue: str,
    walltime: str,
    modules: str,
    workdir: str,
    array_range: str,
    command: str,
) -> str:
    mod_lines = "\n".join(f"module load {m}" for m in modules.split()) if modules.strip() else "# module load ..."
    return f"""You are helping a user run an **SGE array job** on BU SCC (see TechWeb “Batch Script Examples” → Array Job Script).

Write a **complete qsub script** using **#$ -t {array_range}**.

Requirements:
- `#!/bin/bash -l`
- **#$ -P {project}**
- **#$ -l h_rt={walltime}**
- **#$ -N {job_name}**
- **#$ -t {array_range}**
- Optional queue:
{_queue_lines(queue)}
- Echo useful diagnostics with **$JOB_ID**, **$JOB_NAME**, **$SGE_TASK_ID** (TechWeb shows patterns with `echo`).
- Teach how to pick the *n*th input (bash array indexing with `$SGE_TASK_ID` is common in SCC examples).
- `module purge` then:
{mod_lines}
- Working directory:
{_cd_block(workdir)}
- Per-task workload intent:
{command}

Language-specific reminders from SCC docs (include as brief comments in the script):
- Python: `id = os.getenv("SGE_TASK_ID")`
- R: `id <- as.numeric(Sys.getenv("SGE_TASK_ID"))`
- MATLAB: `id = str2num(getenv('SGE_TASK_ID'));`

Output **only** the shell script.
"""
