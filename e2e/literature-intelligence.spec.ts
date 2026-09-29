import { test, expect } from '@playwright/test';
import { encodeAuthToken } from '../lib/auth';

const ownerId = process.env.HELIXMIND_E2E_OWNER_ID;
const investigationId = process.env.HELIXMIND_E2E_INVESTIGATION_ID;

test('investigation literature links publications, evidence, graph, coverage and snapshots', async ({ page, context }) => {
  test.skip(!ownerId || !investigationId, 'Run the real isolated CRISPR workflow and provide its owner/investigation IDs.');
  const token = await encodeAuthToken({ token: { sub: ownerId, role: 'USER' } });
  await context.addCookies([{ name: 'next-auth.session-token', value: token, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' }]);

  await page.goto(`/investigations/${investigationId}/literature`);
  await expect(page.getByRole('heading', { name: 'Literature landscape.' })).toBeVisible();
  await expect(page.getByText(/Relevance is deterministic investigation linkage/)).toBeVisible();

  const result = await page.evaluate(async (id) => {
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/literature/intelligence`);
    return response.json();
  }, investigationId);
  const linkedPublication = result.publications.find((item: { counts: { relationships: number; entities: number } }) => item.counts.relationships > 0 && item.counts.entities > 0);
  expect(linkedPublication, 'real run should contain at least one publication connected to the graph').toBeTruthy();
  const firstPublication = page.locator('.paper-card').filter({ hasText: linkedPublication.title }).first();
  await expect(firstPublication).toBeVisible();
  const titleLink = firstPublication.locator('h3 a');
  await titleLink.click();
  await expect(page.getByRole('heading', { name: 'Evidence contribution' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Connected records' })).toBeVisible();
  await expect(page.getByText(/Deterministic retrieval and investigation-linkage/)).toBeVisible();

  const graphLink = page.getByRole('link', { name: /Inspect supporting publications/ }).first();
  await expect(graphLink).toBeVisible();
  await graphLink.click();
  await expect(page.getByRole('heading', { name: 'Supporting publications.' })).toBeVisible();
  await expect(page.getByText(/persisted evidence/)).toBeVisible();

  const linkedEntityId = linkedPublication.contributions.relationships[0].subjectEntityId;
  const entity = linkedPublication.contributions.entities.find((item: { id: string }) => item.id === linkedEntityId);
  expect(entity, 'linked relationship should reference a persisted investigation entity').toBeTruthy();
  await page.goto(`/knowledge?investigationId=${investigationId}&entityId=${entity.id}`);
  await expect(page.getByRole('heading', { name: 'Knowledge graph.' })).toBeVisible();
  const graph = page.getByRole('img', { name: 'Source-grounded scientific knowledge graph' });
  await expect(graph).toBeVisible();
  await expect(page.getByRole('heading', { name: entity.name })).toBeVisible();
  await expect(page.getByText(/Open publication contribution/).first()).toBeVisible();
  await page.getByText(/Open publication contribution/).first().click();
  await expect(page.getByRole('heading', { name: 'Evidence contribution' })).toBeVisible();

  await page.goto(`/investigations/${investigationId}/literature`);
  if (await page.getByRole('heading', { name: 'Compare immutable snapshots' }).count()) {
    await page.getByRole('button', { name: 'Compare' }).click();
    await expect(page.getByText(/retained publications/)).toBeVisible();
  }
});
