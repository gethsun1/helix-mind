import { test, expect } from '@playwright/test';
import { encodeAuthToken } from '../lib/auth';

const ownerId = process.env.HELIXMIND_E2E_OWNER_ID;
const investigationId = process.env.HELIXMIND_E2E_INVESTIGATION_ID;

test('submission journey exposes real investigation, evidence, memory, reproducibility and asset states', async ({ page, context }) => {
  test.setTimeout(90_000);
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
  await expect(page.getByText(/^Run lineage ·/)).toBeVisible();
  await page.getByText(/^Run lineage ·/).click();
  await expect(page.getByRole('heading', { name: 'Snapshot and research exports' })).toBeVisible();
  await expect(page.getByText(/Scientific reasoning and evidence explorer ·/)).toBeVisible();
  await page.getByText(/Scientific reasoning and evidence explorer ·/).click();
  await expect(page.getByRole('heading', { name: 'Why the evidence points where it does.' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Investigation research tools' }).getByRole('link', { name: /Scientific IP/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Latest research state' })).toBeVisible();
  await expect(page.getByText(/private asset recorded|private assets ·/i)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await expect(page.getByRole('navigation', { name: 'Investigation research tools' }).getByRole('link', { name: /Literature/ })).toBeVisible();

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
  const audit = page.locator('details.audit-disclosure');
  const expectedEventCount = api.find(result => result.path === `/api/backend/api/v1/investigations/${investigationId}`)?.body.events.length ?? 0;
  await expect(audit).not.toHaveAttribute('open', '');
  await audit.locator('summary').click();
  await expect(audit).toHaveAttribute('open', '');
  await expect(audit.locator('.timeline-item')).toHaveCount(expectedEventCount);
  await audit.locator('summary').click();
  await expect(audit).not.toHaveAttribute('open', '');
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

  const assetConsoleErrors: string[] = [];
  page.on('console', message => { if (message.type() === 'error' && /\/api\/backend\/.*assets|scientific asset/i.test(message.text())) assetConsoleErrors.push(message.text()); });
  page.on('pageerror', error => assetConsoleErrors.push(error.message));
  const assetResponsePromise = page.waitForResponse(response => response.url().endsWith(`/api/backend/api/v1/investigations/${investigationId}/assets`) && response.request().method() === 'GET');
  await page.goto(`/investigations/${investigationId}/assets`);
  const assetResponse = await assetResponsePromise;
  const assetBody = await assetResponse.json();
  expect({ url: new URL(assetResponse.url()).pathname, method: assetResponse.request().method(), status: assetResponse.status(), shape: Array.isArray(assetBody) ? `array(${assetBody.length})` : typeof assetBody }).toEqual({ url: `/api/backend/api/v1/investigations/${investigationId}/assets`, method: 'GET', status: 200, shape: 'array(0)' });
  await expect(page.getByRole('heading', { name: 'Scientific asset provenance.' })).toBeVisible();
  await expect(page.getByText('No asset records exist for this Investigation.')).toBeVisible();
  await expect(page.getByText(/legal ownership are assessed separately/i)).toBeVisible();
  await expect(page.getByText('Scientific asset records could not be loaded.')).toHaveCount(0);
  expect(assetConsoleErrors).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: 'Scientific asset provenance.' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
