---
meta:
  uri: scc://quickstart/guide
  name: SCC quickstart (high level)
  description: Orientation steps for new BU SCC users before submitting Slurm jobs.
  mime_type: text/markdown
---

# BU SCC quickstart (checklist)

1. **Access** — Use SSH to the SCC login nodes with your BU Kerberos credentials (see the official SCC access guide for hostnames and Duo/MFA steps).
2. **Software** — Use `module avail` and `module load` to pick a compiler or framework stack; avoid mixing unrelated stacks in one job.
3. **Accounts** — Know your Slurm **account string** (`#SBATCH -A`) from your PI or allocation; wrong accounts fail at submit time.
4. **Filesystems** — Keep large job I/O on **scratch** or **project** space; keep home for code and small configs.
5. **Submit** — Write a batch script with `#SBATCH` headers, then `sbatch script.sh`. Track jobs with `squeue -u $USER`.
6. **Docs** — Use the `search_docs` tool in this MCP server against your ingested documentation collection for up-to-date policy and examples.

When in doubt, open a ticket with Research Computing Services and include your job id, partition, and the last ~30 lines of the Slurm output file.
