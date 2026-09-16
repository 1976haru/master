from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_queue_child_uses_existing_v39_engine_and_suppresses_messageboxes():
    text = (ROOT / "scripts" / "queue_worker.py").read_text(encoding="utf-8")
    assert "Suno15_Mastering_v3_9.pyw" in text
    assert "AppV39()" in text
    assert "messagebox.showinfo = lambda" in text
    assert "messagebox.showwarning = lambda" in text
    assert "messagebox.showerror = lambda" in text


def test_queue_output_uses_job_id_without_changing_dsp_path():
    text = (ROOT / "Suno15_Mastering_v3_9.pyw").read_text(encoding="utf-8")
    assert "queue_job_id" in text
    assert "_JOB_" in text


def test_v310_dynamic_loader_registers_module_before_exec():
    text = (ROOT / "Suno15_Mastering_v3_10.pyw").read_text(encoding="utf-8")
    assert "import sys" in text
    assert text.index("sys.modules[loader.name] = module") < text.index("loader.exec_module(module)")


def test_queue_worker_dynamic_loader_registers_module_before_exec():
    text = (ROOT / "scripts" / "queue_worker.py").read_text(encoding="utf-8")
    assert "sys.modules[loader.name] = module" in text
    assert text.index("sys.modules[loader.name] = module") < text.index("loader.exec_module(module)")
