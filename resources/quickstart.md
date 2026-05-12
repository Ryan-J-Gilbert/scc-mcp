---
meta:
  uri: scc://quickstart/guide
  name: SCC quickstart (high level)
  description: Orientation for BU SCC users—SGE (qsub), modules, scratch, and documentation search.
  mime_type: text/markdown
---

# BU SCC quickstart (checklist)

1. **Access** — SSH to the SCC login hosts with BU Kerberos; follow current ITS guidance for MFA/Duo and hostnames.
2. **Software** — Use `module avail` / `module load`. In **qsub** batch scripts that call `module`, start the script with **`#!/bin/bash -l`** (login shell) per TechWeb.
3. **Project** — Know your SCC **project** string for **`#$ -P project_name`**. Some affiliations (e.g. Med.Campus-associated projects) require **`-P`** on every job.
4. **Submit** — Write a script with **`#$`** directives (walltime **`#$ -l h_rt=…`**, name, mail, PE, GPUs, etc.), then run **`qsub script.sh`**. Track jobs with **`qstat`**; cancel with **`qdel`**.
5. **Parallel work** — OpenMP / threaded jobs: **`-pe omp N`** and often `OMP_NUM_THREADS=$NSLOTS`. MPI: **`mpi_28_tasks_per_node`** or **`mpi_64_tasks_per_node`** with **`mpirun -np $NSLOTS`**. Interactive MPI debugging: **`qrsh -pe mpi_…`** (see “Running MPI jobs in an Interactive Session”).
6. **Scratch & I/O** — High-volume temporary I/O belongs on **per-node `/scratch`** or **`$TMPDIR`**; remember scratch is purged on a **31-day** policy. Project space for shared datasets and final outputs.
7. **Docs** — Use the **`search_docs`** tool here: it searches ingested BU TechWeb SCC pages (scheduling, batch examples, GPUs, etc.).

When you need human help, contact **help@scc.bu.edu** and include **JOB_ID**, **`#$` options**, and the tail of your **`.o` / `.e`** job log files.
