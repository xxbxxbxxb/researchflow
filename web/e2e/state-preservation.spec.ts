import { test, expect } from '@playwright/test';
import { login, createProject, uploadPDF, startResearch } from './helpers';

test('progress refresh preserves scrolling, the evidence drawer and unsaved text', async ({ page }) => {
  await login(page);
  const pid = await createProject(page);
  await uploadPDF(page);
  await startResearch(page);
  await expect(page.getByText('研究已完成', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: '查看报告' }).first().click();
  await page.getByRole('button', { name: '查看原文' }).first().click();
  const unsaved = '正在编辑，不能被进度更新覆盖';
  await page.getByLabel('后续研究问题').fill(unsaved);
  await page.evaluate(() => window.scrollTo(0, 250));
  const original = await page.evaluate(() => window.scrollY);
  const reportId = new URL(page.url()).pathname.split('/').pop()!;
  const report = await (await page.request.get(`/api/reports/${reportId}?project_id=${pid}`)).json();
  const session = await (await page.request.get('/api/auth/session')).json();
  const started = await page.request.post(`/api/tasks/${report.task_id}/runs`, { data: { project_id: pid, mode: 'demo' }, headers: { 'origin': 'http://localhost:5173', 'x-csrf-token': session.csrf_token, 'idempotency-key': `background-${reportId}` } });
  expect(started.status()).toBe(201);
  await expect(page.getByRole('link', { name: '有更新的报告' })).toBeVisible(); // actual new Worker/SSE activity
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - original)).toBeLessThan(2);
  await expect(page.getByTestId('evidence-drawer')).toBeVisible();
  await expect(page.getByLabel('后续研究问题')).toHaveValue(unsaved);
  await page.reload();
  await expect(page.getByLabel('后续研究问题')).toHaveValue(unsaved);
  await expect(page.getByTestId('evidence-drawer')).toBeVisible();
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - original)).toBeLessThan(2);
  await page.getByRole('button', { name: '关闭原文' }).click();
  await page.goto(`/projects/${pid}?tab=tasks&status=succeeded`);
  await page.getByRole('link', { name: '查看任务' }).first().click();
  await page.goBack();
  await expect(page.getByLabel('运行筛选')).toHaveValue('succeeded');
});

test('double start and refresh keep a single durable run', async ({ page }) => {
  await login(page);
  const pid = await createProject(page);
  await uploadPDF(page);
  await page.getByLabel('研究问题').fill('sample size?');
  await page.getByRole('button', { name: '创建研究任务' }).click();
  await page.getByRole('button', { name: '开始研究', exact: true }).dblclick();
  await expect(page.getByText('研究已完成', { exact: true })).toBeVisible();
  await page.reload();
  const runs = await page.request.get(`/api/projects/${pid}/runs`);
  expect((await runs.json()).length).toBe(1);
});
