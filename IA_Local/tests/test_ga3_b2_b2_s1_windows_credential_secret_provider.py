from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "IA_Local" / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(
        0,
        str(SCRIPTS),
    )


from enterprise_sql_gateway import (
    EnterpriseSecretStore,
    EnterpriseSqlError,
    WindowsCredentialSecretProvider,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)

    print(
        "PASS",
        name,
        flush=True,
    )


check(
    "windows_platform",
    os.name == "nt",
)


reference = (
    "sql:"
    + uuid.uuid4().hex
)

secret_a = (
    "Clave-ñ-"
    + uuid.uuid4().hex
)

secret_b = (
    "Rotada-á-"
    + uuid.uuid4().hex
)


provider_a = WindowsCredentialSecretProvider()
target = provider_a.target_name(reference)

check(
    "opaque_target_prefix",
    target.startswith(
        "IA_EMPRESARIAL_LOCAL/sql/"
    ),
)

check(
    "reference_not_exposed_in_target",
    reference not in target,
)

check(
    "secret_not_exposed_in_target",
    secret_a not in target
    and secret_b not in target,
)


created = False

try:
    store_a = EnterpriseSecretStore(
        provider_a
    )

    store_a.set(
        reference,
        secret_a,
    )

    created = True

    check(
        "initial_roundtrip",
        store_a.get(reference)
        == secret_a,
    )

    # New provider/store instance models a process restart.
    provider_b = WindowsCredentialSecretProvider()
    store_b = EnterpriseSecretStore(
        provider_b
    )

    check(
        "restart_roundtrip",
        store_b.get(reference)
        == secret_a,
    )

    # Rotation replaces the existing protected value.
    store_b.set(
        reference,
        secret_b,
    )

    provider_c = WindowsCredentialSecretProvider()
    store_c = EnterpriseSecretStore(
        provider_c
    )

    check(
        "rotation_persisted",
        store_c.get(reference)
        == secret_b,
    )

    check(
        "old_secret_replaced",
        store_c.get(reference)
        != secret_a,
    )

    store_c.delete(
        reference
    )

    created = False

    provider_d = WindowsCredentialSecretProvider()

    check(
        "provider_missing_returns_none",
        provider_d.get(reference)
        is None,
    )

    try:
        EnterpriseSecretStore(
            provider_d
        ).get(reference)

    except EnterpriseSqlError as exc:
        check(
            "store_missing_fails_closed",
            exc.code
            == "SQL_SECRET_UNAVAILABLE",
        )

    else:
        raise AssertionError(
            "store_missing_did_not_fail_closed"
        )

    # Idempotent cleanup.
    provider_d.delete(reference)

    check(
        "delete_idempotent",
        True,
    )

finally:
    if created:
        try:
            WindowsCredentialSecretProvider().delete(
                reference
            )
        except Exception:
            pass

    secret_a = None
    secret_b = None


# Production composition root must use the same secure boundary.
previous_root = os.environ.get(
    "IA_LOCAL_ROOT"
)

with tempfile.TemporaryDirectory() as td:
    product_root = Path(td)
    runtime_root = (
        product_root
        / "IA_Local"
    )

    runtime_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        product_root
        / "RELEASE_METADATA.json"
    ).write_text(
        json.dumps({
            "schema_version": 1,
            "product":
                "IA_EMPRESARIAL_LOCAL",
            "product_version":
                "8.5.5",
            "release":
                "r10.21f",
            "channel":
                "stable",
        }),
        encoding="utf-8",
    )

    os.environ[
        "IA_LOCAL_ROOT"
    ] = str(
        runtime_root
    )

    import analizador_universal as analyzer

    analyzer.configure_sql_admin_services()

    (
        _admin_store,
        admin_provider,
        admin_secrets,
    ) = analyzer._sql_admin_services()

    check(
        "admin_uses_windows_provider",
        isinstance(
            admin_secrets.provider,
            WindowsCredentialSecretProvider,
        ),
    )

    check(
        "admin_provider_uses_same_store",
        admin_provider.secret_store
        is admin_secrets,
    )

    executor = analyzer._sql_executor()

    check(
        "executor_has_provider",
        executor.provider
        is not None,
    )

    check(
        "executor_has_secret_store",
        executor.provider.secret_store
        is not None,
    )

    check(
        "executor_uses_windows_provider",
        isinstance(
            executor.provider.secret_store.provider,
            WindowsCredentialSecretProvider,
        ),
    )


    # Mirror the production application shutdown lifecycle before
    # TemporaryDirectory removes the Windows-backed Qdrant files.
    analyzer.ENTERPRISE_COMPONENTS.vectors.close()

    from enterprise_ai.observability import shutdown_logging

    shutdown_logging()


if previous_root is None:
    os.environ.pop(
        "IA_LOCAL_ROOT",
        None,
    )
else:
    os.environ[
        "IA_LOCAL_ROOT"
    ] = previous_root


gateway_source = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_sql_gateway.py"
).read_text(
    encoding="utf-8"
)

provider_section = gateway_source.split(
    "class WindowsCredentialSecretProvider:",
    1,
)[1].split(
    "def public_sql_profile",
    1,
)[0]

check(
    "credential_manager_api_used",
    "CredWrite"
    in provider_section
    and "CredRead"
    in provider_section
    and "CredDelete"
    in provider_section,
)

check(
    "no_plaintext_file_writer",
    "write_text("
    not in provider_section
    and "write_bytes("
    not in provider_section
    and "open("
    not in provider_section,
)

print(
    "PASS GA.3-B2-B2-S1 WINDOWS CREDENTIAL PROVIDER",
    flush=True,
)
