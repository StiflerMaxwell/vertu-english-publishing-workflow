import assert from 'node:assert/strict';
import {test} from 'node:test';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolveVvvConfig, pushVvvMessage} from '../vertu-vvv-notify.js';

const root = fileURLToPath(new URL('../../', import.meta.url));
const synthetic = {
  VERTU_VVV_APP_ID: 'vbot_' + 'ci',
  VERTU_VVV_APP_SECRET: '',
  VERTU_VVV_CHANNEL_ID: ['0'.repeat(8), '0'.repeat(4), '0'.repeat(4), '0'.repeat(4), '0'.repeat(12)].join('-'),
  VERTU_VVV_PUSH_ENDPOINT: 'https://notify.example.invalid/preview',
};

test('missing notification configuration fails closed', () => {
  assert.throws(() => resolveVvvConfig({}), /VVV_CONFIG_MISSING_APP_ID/);
});

test('preview works with synthetic settings without a send', () => {
  const run = spawnSync(process.execPath, [
    '--import', 'tsx', 'scripts/vertu-vvv-notify.ts', '--preview',
    '--body-file', 'templates/creator-submission.md',
  ], {cwd: root, env: {...synthetic}, encoding: 'utf8'});
  assert.equal(run.status, 0, run.stderr);
  const receipt = JSON.parse(run.stdout);
  assert.equal(receipt.status, 'PREVIEW');
  assert.equal(receipt.http_status, null);
  assert.equal(receipt.delivered_at, null);
});

test('send without secret fails before network activity', () => {
  const run = spawnSync(process.execPath, [
    '--import', 'tsx', 'scripts/vertu-vvv-notify.ts', '--send',
    '--body-file', 'templates/creator-submission.md',
  ], {cwd: root, env: {...synthetic}, encoding: 'utf8'});
  assert.notEqual(run.status, 0);
  assert.match(run.stderr + run.stdout, /SECRET_UNAVAILABLE/);
});

test('missing secret cannot call the transport', async () => {
  let calls = 0;
  const receipt = await pushVvvMessage({body: 'test only', config: resolveVvvConfig(synthetic),
    fetchImpl: (async () => { calls++; throw new Error('Network must not be called'); }) as typeof fetch});
  assert.equal(calls, 0);
  assert.equal(receipt.status, 'FAILED');
  assert.equal(receipt.error, 'VVV_APP_SECRET_UNAVAILABLE');
});
