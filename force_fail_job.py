import sys
from context_foundry.daemon.store import Store
from context_foundry.daemon.models import JobStatus
from context_foundry.daemon.config import Config


def force_fail_job(job_id):
    config = Config.load()
    store = Store(config.db_path)

    job = store.get_job(job_id)
    if not job:
        print(f"Job {job_id} not found")
        return

    print(f"Current status: {job.status}")

    store.update_job_status(
        job_id, JobStatus.CANCELLED, error="Force cancelled by admin script"
    )
    print(f"Job {job_id} marked as CANCELLED")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python force_fail_job.py <job_id>")
        sys.exit(1)

    force_fail_job(sys.argv[1])
