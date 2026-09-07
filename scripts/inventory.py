import argparse
import ast
import csv
import inspect
import io
from pathlib import Path
import textwrap

from scripts.test_environment import configure_test_environment


REQUIREMENTS = {
    "auditoria": "OPS-06 Auditoria com escopo e paginacao",
    "process_health": "OPS-06 Saude do processo",
    "critical_readiness": "OPS-06 Banco e storage",
    "metrics": "OPS-06 Metricas protegidas",
    "ciclos": "FIN-REL-05 Ciclos financeiros e privacidade",
    "health": "OPS-01 Disponibilidade",
    "auth": "AUTH-01 Autenticacao",
    "main": "UI-01 Navegacao operacional",
    "platform": "SAAS-01 Administracao de tenants",
    "produto": "CAD-01 Produtos",
    "categoria": "CAD-02 Categorias",
    "funcionario": "CAD-03 Funcionarios",
    "role": "AUTH-02 Roles",
    "permission": "AUTH-03 Permissoes",
    "cliente": "REL-01 Clientes e cashback",
    "cupom": "CAD-04 Cupons",
    "adiantamento": "FIN-01 Adiantamentos",
    "estoque": "EST-01 Estoque e alertas",
    "pdv": "PDV-01 Vendas e cancelamentos",
    "financeiro": "FIN-02 Lancamentos e fechamento",
    "import_export": "CAD-05 Importacao e exportacao",
    "boleto": "FORA-01 Bancario",
    "fiscal": "FORA-02 Fiscal",
}


def service_calls(tree):
    return {
        f"{node.func.value.id}.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id.endswith("Service")
    }


def render_inventory():
    configure_test_environment()
    from app import create_app

    test_services = {}
    for filename in sorted(Path("tests").glob("test_*.py")):
        tree = ast.parse(filename.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if isinstance(function, ast.FunctionDef) and function.name.startswith("test_"):
                for service in service_calls(function):
                    test_services.setdefault(service, set()).add(f"{filename.as_posix()}::{function.name}")
    app = create_app()
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["requisito", "metodos", "rota", "endpoint", "servicos_diretos", "testes_de_servico_indiretos", "observacao"])
    for rule in sorted(app.url_map.iter_rules(), key=lambda entry: (entry.rule, entry.endpoint)):
        if rule.endpoint == "static":
            continue
        view = inspect.unwrap(app.view_functions[rule.endpoint])
        services = service_calls(ast.parse(textwrap.dedent(inspect.getsource(view))))
        tests = set().union(*(test_services.get(service, set()) for service in services))
        blueprint = rule.endpoint.split(".")[0]
        requirement = REQUIREMENTS[blueprint]
        writer.writerow([
            requirement, "|".join(sorted(rule.methods - {"OPTIONS", "HEAD"})), rule.rule,
            rule.endpoint, "|".join(sorted(services)) or "template/decorator/helper/consulta direta",
            "|".join(sorted(tests)) or "LACUNA: sem teste direto de servico localizado",
            "Fora do escopo funcional; testes existentes preservados" if requirement.startswith("FORA")
            else "Vinculo estatico de servico; nao comprova cobertura HTTP desta rota",
        ])
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path("docs/04-modulos-e-funcionalidades/inventario-requisito-rota-servico-teste.csv")
    inventory = render_inventory()
    if args.check:
        if destination.read_text(encoding="utf-8") != inventory:
            raise SystemExit("Inventario desatualizado; execute python -m scripts.inventory.")
    else:
        destination.write_text(inventory, encoding="utf-8", newline="")
    print(f"Inventario OK: {len(inventory.splitlines()) - 1} rotas")


if __name__ == "__main__":
    main()
