"""Cablage du coordinator et du frontend, verifie par analyse syntaxique.

Home Assistant n'est pas installe dans le banc de test : on verifie que le
code de production appelle bien les fonctions testees (lecon SRM).
"""

from __future__ import annotations

import ast
import os

PKG = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "printer_maintenance"
)


def _tree(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as handle:
        return ast.parse(handle.read())


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == name
        ):
            return node
    raise AssertionError(name)


def _calls(node):
    return {
        (sub.func.attr if isinstance(sub.func, ast.Attribute) else sub.func.id)
        for sub in ast.walk(node)
        if isinstance(sub, ast.Call) and isinstance(sub.func, (ast.Attribute, ast.Name))
    }


def test_handler_utilise_classify_transition():
    handler = _func(_tree("coordinator.py"), "_handle_status_change")
    assert "classify_transition" in _calls(handler)


def test_dernier_etat_reel_persiste():
    source = ast.unparse(_tree("coordinator.py"))
    assert "last_status" in source


def test_migration_branchee():
    init = _tree("__init__.py")
    migrate = _func(init, "async_migrate_entry")
    assert "migrate_options_1_2" in _calls(migrate)


def test_frontend_sans_lecture_de_fichier_bloquante():
    tree = _tree("frontend.py")
    calls = _calls(tree)
    assert "read_text" not in calls
    assert "open" not in calls
    assert "async_get_integration" in calls
