import { test, expect } from '@playwright/test';
import { encodeAuthToken } from '../lib/auth';

const ownerId = process.env.HELIXMIND_E2E_OWNER_ID;
const investigationId = process.env.HELIXMIND_E2E_INVESTIGATION_ID;

test('submission journey exposes real investigation, evidence, memory, reproducibility and asset states', async ({ page, context }) => {
  test.skip(!ownerId || !investigationId, 'Use the isolated HelixMind test database owner and CRISPR investigation IDs.');
  const token = await encodeAuthToken({ token: { sub: ownerId, role: 'USER' } });
  await context.addCookies([{ name: 'next-auth.session-token', value: token, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' }]);

  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /research workspace/i })).toBeVisible();
  await expect(page.getByText('Total investigations')).toBeVisible();

  await page.goto('/investigations');
  await expect(page.getByRole('heading', { name: 'Your investigations.' })).toBeVisible();
  await expect(page.getByText('CRISPR-Cas9 and sickle-cell disease literature intelligence verification')).toBeVisible();

  await page.goto(`/investigations/${investigationId}`);
  await expect(page.getByRole('heading', { name: 'CRISPR-Cas9 and sickle-cell disease literature intelligence verification' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Persistent Research Memory' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Run lineage' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Snapshot and research exports' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Why the evidence points where it does.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Research asset record' })).toBeVisible();

  const api = await page.evaluate(async id => {
    const paths = [
      `/api/backend/api/v1/investigations/${id}`,
      `/api/backend/api/v1/investigations/${id}/papers?page=1&pageSize=8`,
      `/api/backend/api/v1/investigations/${id}/runs`,
      `/api/backend/api/v1/investigations/${id}/snapshots`,
      `/api/backend/api/v1/investigations/${id}/memories`,
      `/api/backend/api/v1/investigations/${id}/literature/semantic-extractions`,
      `/api/backend/api/v1/investigations/${id}/literature/intelligence`,
      `/api/backend/api/v1/investigations/${id}/knowledge?limit=200`,
      `/api/backend/api/v1/investigations/${id}/hypotheses`,
      `/api/backend/api/v1/investigations/${id}/reasoning`,
      `/api/backend/api/v1/investigations/${id}/assets`,
    ];
    return Promise.all(paths.map(async path => { const response = await fetch(path); return { path, status: response.status, body: response.ok ? await response.json() : null }; }));
  }, investigationId);
  expect(api.map(result => result.status), JSON.stringify(api.map(result => `${result.path}: ${result.status}`))).toEqual(api.map(() => 200));
  const semantic = api.find(result => result.path.endsWith('/semantic-extractions'))?.body.extractions;
  expect(semantic.length).toBeGreaterThan(0);
  expect(semantic.some((candidate: { validationStatus: string; graphRelationshipId: string | null }) => candidate.validationStatus === 'VALID' && candidate.graphRelationshipId)).toBeTruthy();
  expect(api.find(result => result.path.endsWith('/snapshots'))?.body.length).toBeGreaterThan(0);
  expect(api.find(result => result.path.endsWith('/assets'))?.body).toEqual([]);
  expect(api.find(result => result.path.endsWith('/memories'))?.body).toEqual([]);

  await page.goto(`/investigations/${investigationId}/literature`);
  await expect(page.getByRole('heading', { name: 'Literature landscape.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Semantic extraction pilot' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /CRISPR/i }).first()).toBeVisible();

  await page.goto(`/knowledge?investigationId=${investigationId}`);
  await expect(page.getByRole('heading', { name: 'Knowledge graph.' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Source-grounded scientific knowledge graph' })).toBeVisible();

  await page.goto('/hypotheses');
  await expect(page.getByRole('heading', { name: 'Hypothesis lab.' })).toBeVisible();

  await page.goto(`/investigations/${investigationId}/assets`);
  await expect(page.getByRole('heading', { name: 'Scientific asset provenance.' })).toBeVisible();
  await expect(page.getByText('No asset records exist for this Investigation.')).toBeVisible();
  await expect(page.getByText(/legal ownership are assessed separately/i)).toBeVisible();
});
