"""Tests de la machine a etats d'impression (v0.0.6).

Constats du 21/11/2026 : PrusaLink publie l'etat « finished », absent des
etats termines par defaut, donc 0 travail reussi compte ; une coupure
« unavailable » pendant une impression cloturait la session.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "custom_components", "printer_maintenance"
    ),
)

from session import (  # noqa: E402
    DEFAULT_COMPLETED,
    classify_transition,
    migrate_options_1_2,
)

PRINTING = ["printing", "impression"]
PAUSED = ["paused", "pause"]
COMPLETED_OLD = ["completed", "complete", "finish"]
FAILURE = ["stopped", "error", "cancelled", "failed"]


def _c(prev, new, completed=None):
    return classify_transition(
        prev, new, PRINTING, PAUSED, completed or DEFAULT_COMPLETED, FAILURE
    )


def test_finished_est_un_etat_termine_par_defaut():
    assert "finished" in DEFAULT_COMPLETED
    assert _c("printing", "finished") == "end_ok"


def test_ancienne_config_ne_compte_pas_finished():
    """Reproduit le bug : avec la config enregistree, finished n'est pas OK."""
    assert _c("printing", "finished", COMPLETED_OLD) == "end_other"


def test_migration_ajoute_finished_aux_options():
    options = {"completed_states": list(COMPLETED_OLD), "x": 1}
    migrated = migrate_options_1_2(options)
    assert "finished" in migrated["completed_states"]
    assert migrated["x"] == 1
    assert options["completed_states"] == COMPLETED_OLD  # entree intacte


def test_migration_sans_doublon_ni_cle_absente():
    assert migrate_options_1_2({"completed_states": ["finished"]})[
        "completed_states"
    ] == ["finished"]
    assert "completed_states" not in migrate_options_1_2({"x": 1})


def test_unavailable_pendant_impression_ignore():
    assert _c("printing", "unavailable") == "ignore"
    assert _c("printing", "unknown") == "ignore"


def test_retour_apres_coupure_ne_redemarre_pas():
    """L'etat precedent retenu est le dernier etat reel (printing)."""
    assert _c("printing", "printing") == "none"


def test_cycle_complet():
    assert _c("idle", "printing") == "start"
    assert _c("printing", "paused") == "pause"
    assert _c("paused", "printing") == "resume"
    assert _c("printing", "stopped") == "end_ko"
    assert _c("paused", "idle") == "end_other"
    assert _c("idle", "finished") == "none"
