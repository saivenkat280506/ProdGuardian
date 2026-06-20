from prodguardian.scanner.rules.cors_exposure import CORSEndpointRule
from prodguardian.scanner.rules.debug_endpoints import DebugEndpointsRule
from prodguardian.scanner.rules.hardcoded_secrets import HardcodedSecretsRule
from prodguardian.scanner.rules.missing_env import MissingEnvVarRule
from prodguardian.scanner.rules.prod_leakage import ProdLeakageRule
from prodguardian.scanner.rules.sql_injection import SQLInjectionRule
from prodguardian.scanner.rules.unsafe_eval import UnsafeEvalRule

ALL_RULES = [
    HardcodedSecretsRule(),
    MissingEnvVarRule(),
    DebugEndpointsRule(),
    SQLInjectionRule(),
    UnsafeEvalRule(),
    CORSEndpointRule(),
    ProdLeakageRule(),
]


def run_rules(ast_data):
    """Run all rules against parsed AST data and return list of issues."""
    if ast_data is None:
        return []
    issues = []
    for rule in ALL_RULES:
        try:
            for issue in rule.check(ast_data):
                issue["rule_id"] = rule.id
                issue["severity"] = rule.severity
                issue["file"] = ast_data.get("path", "unknown")
                issues.append(issue)
        except Exception as e:
            print(f"Warning: Rule {rule.id} failed: {e}")
    return issues
