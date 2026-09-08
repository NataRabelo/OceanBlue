const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const YAML = require('yaml');

const workflowSource = fs.readFileSync('.github/workflows/ci.yml', 'utf8');
const workflow = YAML.parse(workflowSource);
const compose = YAML.parse(fs.readFileSync('compose.test.yml', 'utf8'));
assert.equal(workflow.name, 'OceanBlue verification');
assert.ok(Object.hasOwn(workflow.on, 'push') && Object.hasOwn(workflow.on, 'pull_request'));
assert.equal(workflow.permissions.contents, 'read');
assert.ok(workflow.jobs.test['timeout-minutes'] >= 30);
const steps = workflow.jobs.test.steps;
assert.ok(steps.some(step => step.run === 'docker compose -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test'));
assert.ok(steps.some(step => step.run?.includes('sh scripts/validate_image.sh oceanblue-production')));
assert.ok(steps.some(step => step.if === 'always()' && step.run?.includes('test:/app/coverage.xml') && step.run?.includes('test:/tmp/junit.xml')));
assert.ok(steps.some(step => step.if === 'always()' && step.run === 'docker compose -f compose.test.yml --profile smoke down -v'));
const command = compose.services.test.command.join(' ');
assert.equal(compose.services.test.shm_size, '1gb');
assert.ok(command.includes('python -m scripts.validate_migrations && python -m pytest --junitxml=/tmp/junit.xml'));
assert.ok(!/--no-cov|--ignore|--deselect| -k /.test(command));
const pytestConfig = fs.readFileSync('pytest.ini', 'utf8');
assert.ok(pytestConfig.includes('testpaths = tests') && pytestConfig.includes('--cov=app') && pytestConfig.includes('--cov-fail-under=50'));
assert.ok(fs.readFileSync('.coveragerc', 'utf8').includes('branch = True'));
console.log(JSON.stringify({workflow: workflow.name, timeout_minutes: workflow.jobs.test['timeout-minutes'],
  full_suite: true, all_migrations: true, coverage_gate_percent: 50, branch_coverage: true,
  test_shared_memory: compose.services.test.shm_size,
  always_collect_evidence: true, always_cleanup: true,
  workflow_sha256: crypto.createHash('sha256').update(workflowSource).digest('hex')}, null, 2));
