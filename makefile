setup:
	python -m venv .venv
	.venv/Scripts/python.exe -m pip install -e .

run:
	.venv/Scripts/python.exe -m src.main

builder:
	.venv/Scripts/python.exe -m aurora_method_builder

check:
	.venv/Scripts/python.exe -m compileall -q src
