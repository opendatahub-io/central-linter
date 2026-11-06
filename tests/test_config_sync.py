"""The pip-shipped lint configs must match the image-baked ones.

lint/config/ is what the pip package ships (local pre-commit use and the
jira-ticket-linter's linterignore); config/ is what the container image
bakes in at /home/linter/.config/ and the make targets fall back to. If
they drift, local runs and CI enforce different rules.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

PAIRS = [
    ("lint/config/.ruff.toml", "config/ruff.toml"),
    ("lint/config/.yamllint.yaml", "config/yamllint.yaml"),
]


def test_shipped_configs_match_image_configs():
    for shipped, image in PAIRS:
        shipped_content = (ROOT / shipped).read_text()
        image_content = (ROOT / image).read_text()
        assert shipped_content == image_content, (
            f"{shipped} and {image} have drifted apart; they must stay identical "
            f"so local pre-commit runs enforce the same rules as the CI image"
        )
