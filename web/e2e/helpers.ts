import { expect, Page } from '@playwright/test';
import path from 'node:path';

export async function login(page: Page) {
  await page.goto('/projects');
  await page.getByLabel('密码', { exact: true }).fill('test-password-1234');
  await page.getByRole('button', { name: '进入工作台' }).click();
  await expect(page.getByRole('heading', { name: '研究项目', exact: true })).toBeVisible();
}

export async function createProject(page: Page) {
  await page.getByRole('button', { name: '新建项目', exact: true }).click();
  const name = `证据研究 ${Date.now()}`;
  await page.getByLabel('项目名称').fill(name);
  await page.getByLabel('项目背景').fill('核对样本量和实验条件。');
  await page.getByRole('button', { name: '创建项目', exact: true }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  return new URL(page.url()).pathname.split('/').pop()!;
}

export async function uploadPDF(page: Page) {
  await page.getByLabel('上传资料').setInputFiles(path.resolve('../artifacts/research-demo.pdf'));
  await expect(page.getByText('research-demo.pdf', { exact: true })).toBeVisible();
}

export async function startResearch(page: Page, mode = 'supported') {
  await page.getByLabel('研究问题').fill('What is the synthetic study sample size?');
  await page.getByLabel('固定演示案例').selectOption(mode);
  await page.getByRole('button', { name: '创建研究任务' }).click();
  await expect(page.getByRole('button', { name: '开始研究', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '开始研究', exact: true }).click();
}
