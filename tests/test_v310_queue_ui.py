from __future__ import annotations

import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace

from haru_mastering.queue_manager import MasteringQueueJob


ROOT = Path(__file__).resolve().parents[1]


def _load_v310_module():
    source = ROOT / "Suno15_Mastering_v3_10.pyw"
    loader = SourceFileLoader("haru_test_v310_ui", str(source))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {source}")
    module = module_from_spec(spec)
    sys.modules[loader.name] = module
    try:
        loader.exec_module(module)
    finally:
        sys.modules.pop(loader.name, None)
    return module


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeQueueManager:
    def __init__(self):
        self.jobs = []
        self.added = None

    def add_job(self, folder, **settings):
        self.added = {"folder": Path(folder), **settings}
        job = MasteringQueueJob("job-1", str(folder), **settings)
        self.jobs.append(job)
        return job


class FakeTree:
    def __init__(self):
        self.items = {}
        self.order = []
        self.selected = ()
        self.y = 0.0
        self.delete_calls = []

    def selection(self):
        return self.selected

    def selection_set(self, *items):
        self.selected = tuple(items)

    def yview(self):
        return (self.y, min(self.y + 0.5, 1.0))

    def yview_moveto(self, fraction):
        self.y = fraction

    def get_children(self):
        return tuple(self.order)

    def exists(self, item):
        return item in self.items

    def delete(self, *items):
        self.delete_calls.extend(items)
        for item in items:
            self.items.pop(item, None)
            if item in self.order:
                self.order.remove(item)

    def insert(self, _parent, _index, iid=None, values=()):
        self.items[iid] = tuple(values)
        self.order.append(iid)
        return iid

    def item(self, item, option=None, **kwargs):
        if "values" in kwargs:
            self.items[item] = tuple(kwargs["values"])
        if option == "values":
            return self.items[item]
        return {"values": self.items[item]}

    def move(self, item, _parent, index):
        if item in self.order:
            self.order.remove(item)
        self.order.insert(index, item)


def test_queue_add_uses_queue_channel_not_hidden_main_channel(tmp_path):
    module = _load_v310_module()
    app = object.__new__(module.AppV310)
    app.channel_var = Value("OLD_POP_LOUNGE")
    app.genre_var = Value("POP")
    app.sound_var = Value("NATURAL")
    app.quality_var = Value("FAST")
    app.queue_channel_var = Value("TOKYO_CHILL")
    app.queue_genre_var = Value("CHILL_RAP")
    app.queue_sound_var = Value("RICH")
    app.queue_quality_var = Value("QUALITY+")
    app.queue_manager = FakeQueueManager()
    app.queue_tree = FakeTree()

    folder = tmp_path / "CHILI_LAB"
    folder.mkdir()
    app._add_queue_folder(folder)

    assert app.queue_manager.added["channel_key"] == "TOKYO_CHILL"
    assert app.queue_manager.added["genre_key"] == "CHILL_RAP"
    assert app.queue_manager.added["sound_mode"] == "RICH"
    assert app.queue_manager.added["quality_mode"] == "QUALITY+"


def test_queue_refresh_preserves_selection_and_updates_rows_incrementally(tmp_path):
    module = _load_v310_module()
    app = object.__new__(module.AppV310)
    first = MasteringQueueJob(
        "job-1",
        str(tmp_path / "first"),
        "TOKYO_CHILL",
        "CHILL_RAP",
        "RICH",
        "QUALITY+",
        current_track=1,
        total_tracks=15,
    )
    second = MasteringQueueJob("job-2", str(tmp_path / "second"), "OLD_POP_LOUNGE", "POP", "NATURAL", "FAST")
    app.queue_manager = SimpleNamespace(jobs=[first, second])
    app.queue_tree = FakeTree()

    app._refresh_queue_tree()
    app.queue_tree.selection_set("job-1")
    app.queue_tree.y = 0.35
    first.current_track = 7
    app._refresh_queue_tree()

    assert app.queue_tree.order == ["job-1", "job-2"]
    assert app.queue_tree.selected == ("job-1",)
    assert app.queue_tree.y == 0.35
    assert app.queue_tree.delete_calls == []
    assert app.queue_tree.items["job-1"][3] == "Tokyo Chill / 일본 20~30대"
    assert app.queue_tree.items["job-1"][4] == "Chill Rap"
    assert app.queue_tree.items["job-1"][7] == "7/15"
