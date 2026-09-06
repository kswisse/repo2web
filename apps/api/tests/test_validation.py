import re
import pytest
from app.services.repository import validate_github_url, extract_owner_repo


def test_valid_github_url():
    assert validate_github_url("https://github.com/user/repo") is True


def test_valid_github_url_with_suffix():
    assert validate_github_url("https://github.com/user/repo.git") is True


def test_valid_github_url_with_path():
    assert validate_github_url("https://github.com/user/repo/tree/main") is True


def test_invalid_url_not_github():
    assert validate_github_url("https://gitlab.com/user/repo") is False


def test_invalid_url_missing_repo():
    assert validate_github_url("https://github.com/user") is False


def test_invalid_url_empty():
    assert validate_github_url("") is False


def test_extract_owner_repo():
    owner, repo = extract_owner_repo("https://github.com/user/myrepo")
    assert owner == "user"
    assert repo == "myrepo"


def test_extract_owner_repo_with_git_suffix():
    owner, repo = extract_owner_repo("https://github.com/user/myrepo.git")
    assert owner == "user"
    assert repo == "myrepo"


def test_extract_owner_repo_invalid():
    with pytest.raises(Exception):
        extract_owner_repo("https://gitlab.com/user/repo")
