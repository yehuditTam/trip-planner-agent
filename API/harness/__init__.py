from pathlib import Path


def logger(file: str):
    """Every runtime action is printed with the name of the harness file that executed it."""
    name = Path(file).name

    def log(msg: str) -> None:
        print(f"[{name}] {msg}", flush=True)
    return log
