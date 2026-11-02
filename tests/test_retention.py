from backend.retention import cleanup_expired_files, delete_upload


def test_delete_upload_rejects_traversal(tmp_path):
    outside = tmp_path.parent / "outside.pdf"
    outside.write_bytes(b"x")
    try:
        assert not delete_upload(tmp_path, "../outside.pdf")
    finally:
        outside.unlink()


def test_cleanup_expired_files_removes_only_old_files(tmp_path):
    old_file = tmp_path / "old.pdf"
    new_file = tmp_path / "new.pdf"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    removed = cleanup_expired_files(
        tmp_path,
        max_age_seconds=60,
        now=200.0,
        mtime=lambda path: 100.0 if path.name == "old.pdf" else 199.0,
    )

    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
