import pytest
from pathlib import Path
from services.store_service import StoreService


# Use pytest fixture for shared setup
@pytest.fixture
def store_service():
    """Provide StoreService instance with default DB path"""
    db_path = Path("~/.context-foundry/cfd/jobs.db").expanduser()
    return StoreService(db_path=db_path)


def test_store_connection(store_service):
    """Verify Store API connection works"""
    jobs, total = store_service.list_jobs(limit=1)
    assert jobs is not None
    assert isinstance(jobs, list)


def test_get_job_by_id(store_service):
    """Verify job retrieval by ID"""
    jobs, total = store_service.list_jobs(limit=1)
    if jobs:
        job = store_service.get_job(jobs[0].id)
        assert job is not None
        assert job.id == jobs[0].id
    else:
        pytest.skip("No jobs available in database")


def test_get_logs(store_service):
    """Verify log retrieval"""
    jobs, total = store_service.list_jobs(limit=1)
    if jobs:
        logs, log_total = store_service.get_logs(jobs[0].id, limit=10)
        assert logs is not None
        assert isinstance(logs, list)
    else:
        pytest.skip("No jobs available in database")
