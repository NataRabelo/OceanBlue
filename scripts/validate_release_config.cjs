const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const YAML = require('yaml');

const source = fs.readFileSync('compose.production.yml', 'utf8');
const compose = YAML.parse(source);
const version = fs.readFileSync('VERSION', 'utf8').trim();
assert.match(version, /^\d+\.\d+\.\d+-rc\.\d+$/);
assert.ok(fs.readFileSync('Dockerfile', 'utf8').includes(`org.opencontainers.image.version="${version}"`));
assert.ok(compose.services.app.image.includes(':?'));
assert.ok(compose.services.proxy.image.includes(':?'));
assert.equal(compose.networks.backend.internal, true);
assert.deepEqual(compose.services.proxy.ports, ['443:8443']);
for (const name of ['app', 'db']) assert.equal(compose.services[name].ports, undefined);
for (const name of ['app', 'proxy']) {
  const service = compose.services[name];
  assert.equal(service.read_only, true);
  assert.notEqual(service.user.split(':')[0], '0');
  assert.deepEqual(service.cap_drop, ['ALL']);
  assert.ok(service.security_opt.includes('no-new-privileges:true'));
  assert.equal(service.logging.options['max-file'], '5');
}
const environment = compose.services.app.environment;
for (const flag of ['FEATURE_BOLETO', 'FEATURE_FISCAL', 'FEATURE_EXTERNAL_PROVIDERS']) assert.equal(environment[flag], 'false');
assert.equal(environment.RUN_MIGRATIONS, 'false');
assert.equal(environment.FORCE_HTTPS, 'true');
assert.equal(environment.FLASK_ENV, 'production');
assert.equal(environment.TRUSTED_PROXY_NETWORKS, `${compose.services.proxy.networks.backend.ipv4_address}/32`);
assert.ok(compose.services.app.volumes.includes('files:/app/instance'));
assert.ok(compose.services.db.volumes.includes('database:/var/lib/postgresql/data'));
assert.equal(compose.services.proxy.depends_on.app.condition, 'service_healthy');
console.log(JSON.stringify({version, production_config_sha256: crypto.createHash('sha256').update(source).digest('hex'),
  flags_fail_closed: true, immutable_image_configuration_required: true, rootless_readonly: true,
  private_database_and_application: true, runtime_migrations_disabled: true,
  proxy_trust_matches_network: true, persistent_database_and_files: true,
  scope: 'Static deployment contract. Installed TLS, secrets, volume durability and operator readiness require installation acceptance.'}, null, 2));
