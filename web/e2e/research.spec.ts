import { test, expect } from '@playwright/test';
import { login, createProject, uploadPDF, startResearch } from './helpers';

test('PDF evidence closes the project, research, knowledge and follow-up path', async ({ page }) => {
  await login(page);
  const project = await createProject(page);
  await uploadPDF(page);
  await startResearch(page);
  await expect(page.getByText('研究已完成', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: '查看报告' }).first().click();
  await expect(page.getByText('固定演示', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('材料支持', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: '查看原文' }).first().click();
  await expect(page.getByTestId('evidence-drawer')).toBeVisible();
  await expect(page.getByTestId('evidence-quote')).toContainText('sample size of 12');
  await page.getByRole('button', { name: '关闭原文' }).click();
  await page.getByRole('button', { name: '接受为项目知识' }).first().click();
  await expect(page.getByText('已保存为项目知识')).toBeVisible();
  await page.getByLabel('后续研究问题').fill('What experimental condition limits this conclusion?');
  await page.getByRole('button', { name: '保存后续草稿' }).click();
  await expect(page.getByText('后续草稿已保存')).toBeVisible();
  await page.goto(`/projects/${project}?tab=knowledge`);
  await expect(page.getByText('What experimental condition limits this conclusion?')).toBeVisible();
  await expect(page.getByRole('button', { name: '启动后续研究' })).toBeVisible();
});

test('invalid citations fail visibly and never acquire a verified conclusion', async ({ page }) => {
  await login(page);
  await createProject(page);
  await uploadPDF(page);
  await startResearch(page, 'invalid-citation');
  await expect(page.getByText('研究未能完成', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '查看报告' })).toHaveCount(0);
  await expect(page.getByText('材料支持', { exact: true })).toHaveCount(0);
});
