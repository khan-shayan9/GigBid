from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "agent" / "config.yaml"


def test_profiles_set_a_model_for_the_same_nodes() -> None:
    models = yaml.safe_load(CONFIG_PATH.read_text())["models"]
    open_nodes = models["profiles"]["open"]["nodes"]
    paid_nodes = models["profiles"]["paid"]["nodes"]
    assert models["profile"] in models["profiles"]
    assert set(open_nodes) == set(paid_nodes)
    assert all(open_nodes.values())
