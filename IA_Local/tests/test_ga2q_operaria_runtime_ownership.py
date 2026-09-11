from __future__ import annotations

import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OPERAR = ROOT / "OperarIA.ps1"

assert OPERAR.is_file(), "OperarIA.ps1 missing"

text = OPERAR.read_text(encoding="utf-8-sig")


def extract_function(source: str, name: str) -> str:
    marker = f"function {name} {{"
    start = source.find(marker)

    assert start >= 0, f"{name} not found"

    brace_start = source.find("{", start)
    assert brace_start >= 0

    depth = 0
    in_single = False
    in_double = False
    escaped = False

    for index in range(brace_start, len(source)):
        ch = source[index]

        if escaped:
            escaped = False
            continue

        if ch == "`":
            escaped = True
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            continue

        if in_single or in_double:
            continue

        if ch == "{":
            depth += 1

        elif ch == "}":
            depth -= 1

            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"unterminated function: {name}")


predicate = extract_function(
    text,
    "Test-AnalyzerCommandLineOwnership",
)

owned_function = extract_function(
    text,
    "Get-OwnedAnalyzerProcess",
)

assert "IA_EMPRESARIAL_LOCAL" not in predicate
assert "IA_EMPRESARIAL_LOCAL" not in owned_function

assert "GetFullPath($Analyzer)" in predicate
assert "[regex]::Escape($expectedAnalyzer)" in predicate
assert "[regex]::IsMatch(" in predicate
assert "IsNullOrWhiteSpace($CommandLine)" in predicate

assert "Test-AnalyzerCommandLineOwnership" in owned_function
assert "Get-CimInstance Win32_Process" in owned_function


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_case(
    *,
    analyzer: str,
    command_line: str,
    expected: bool,
) -> None:
    harness = f"""
$ErrorActionPreference = 'Stop'

$Analyzer = {ps_quote(analyzer)}

{predicate}

$result = Test-AnalyzerCommandLineOwnership `
    -CommandLine {ps_quote(command_line)}

if ($result) {{
    Write-Output 'OWNED=True'
}}
else {{
    Write-Output 'OWNED=False'
}}
"""

    with tempfile.TemporaryDirectory() as tmp:
        script = pathlib.Path(tmp) / "predicate-test.ps1"

        script.write_text(
            harness,
            encoding="utf-8",
            newline="\n",
        )

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    assert completed.returncode == 0, (
        completed.stdout
        + "\n"
        + completed.stderr
    )

    expected_text = (
        "OWNED=True"
        if expected
        else "OWNED=False"
    )

    assert expected_text in completed.stdout, (
        f"expected {expected_text!r}; "
        f"stdout={completed.stdout!r}; "
        f"stderr={completed.stderr!r}"
    )


arbitrary_analyzer = (
    r"C:\Users\Example User\AppData\Local\Temp"
    r"\ga-runtime\installed-product"
    r"\IA_Local\scripts\analizador_universal.py"
)

valid_command = (
    '"C:\\Python312\\python.exe" '
    f'"{arbitrary_analyzer}" '
    "--host 127.0.0.1 --port 8091"
)

run_case(
    analyzer=arbitrary_analyzer,
    command_line=valid_command,
    expected=True,
)

run_case(
    analyzer=arbitrary_analyzer.upper(),
    command_line=valid_command,
    expected=True,
)

run_case(
    analyzer=arbitrary_analyzer,
    command_line=(
        '"C:\\Python312\\python.exe" '
        '"C:\\Other Product\\IA_Local\\scripts'
        '\\analizador_universal.py" '
        "--host 127.0.0.1 --port 8091"
    ),
    expected=False,
)

run_case(
    analyzer=arbitrary_analyzer,
    command_line="",
    expected=False,
)

run_case(
    analyzer=arbitrary_analyzer,
    command_line=(
        '"C:\\Python312\\python.exe" '
        f'"{arbitrary_analyzer}.evil" '
        "--host 127.0.0.1 --port 8091"
    ),
    expected=False,
)

run_case(
    analyzer=arbitrary_analyzer,
    command_line=(
        '"C:\\Python312\\python.exe" '
        '"C:\\Temp\\analizador_universal.py" '
        "--host 127.0.0.1 --port 8091"
    ),
    expected=False,
)

simple_analyzer = (
    r"C:\Temp\IAProduct\IA_Local"
    r"\scripts\analizador_universal.py"
)

run_case(
    analyzer=simple_analyzer,
    command_line=(
        r"C:\Python312\python.exe "
        + simple_analyzer
        + " --host 127.0.0.1 --port 8091"
    ),
    expected=True,
)

print("GA2Q_OPERARIA_RUNTIME_OWNERSHIP: PASS")