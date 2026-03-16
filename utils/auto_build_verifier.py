import argparse
import sys
import subprocess
from pathlib import Path
from common.constants import TASKS_DIR

from harness.evaluation.main import run as run_main

# Wrapper that builds images if needed, then calls the original verifier.
def run_verifier():
    parser = argparse.ArgumentParser(description="Run benchmark tasks.", add_help=False)
    parser.add_argument(
        "--use-local-images",
        action="store_true",
        default=True,
        help="Use local docker images instead of pulling from GCR.",
    )
    # We only parse the arguments we need for building, and let the rest pass through
    parser.add_argument(
        "--tasks-dir", 
        type=Path, 
        default=TASKS_DIR, 
        help="Path to the tasks directory.",
    )
    parser.add_argument(
        "--tasks-filter", 
        "--tasks_filter", 
        type=str, 
        default=None,
        help="Yaml file with instance_ids to filter tasks. Prefix with '!' to negate.",
    )
    parser.add_argument(
        "--task", 
        type=str, 
        default=None, 
        help="Run a single benchmark task by its key (instance_id).",
    )
    parser.add_argument(
        "--max-parallel-containers", 
        type=int, 
        default=4, 
        help="Maximum number of containers to run in parallel on a single machine.",
    )
    
    args, unknown = parser.parse_known_args()

    # Pre-build images before calling into the original harness loop
    if args.use_local_images:
        print("Automatically building required local images...")
        build_cmd = ["uv", "run", "build_images", "--build", "--tasks-dir", str(args.tasks_dir)]
        if getattr(args, "tasks_filter", None):
            build_cmd.extend(["--tasks-filter", args.tasks_filter])
        if getattr(args, "task", None):
            build_cmd.extend(["--task_id", args.task])
        build_cmd.extend(["--max_workers", str(args.max_parallel_containers)])
        
        try:
            subprocess.run(build_cmd, check=True)
        except subprocess.CalledProcessError:
            print("Failed to auto-build Docker images. Aborting verifier.", file=sys.stderr)
            sys.exit(1)

    # Hand over control to original verifier main run
    run_main()

if __name__ == "__main__":
    run_verifier()
